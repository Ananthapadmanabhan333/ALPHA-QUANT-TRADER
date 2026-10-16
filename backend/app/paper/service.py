"""
ALPHA Quant — Phase 5: Paper Trading Application Service.
Orchestrates PaperBroker, MarketData feeds, risk evaluations, and read queries.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.service import MarketDataService
from app.models.market import MarketCandle
from app.models.paper import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperRiskState,
)
from app.paper.broker import PaperBroker
from app.paper.constants import DEFAULT_MAX_FEED_AGE_SECONDS, OrderStatus
from app.paper.exceptions import InvalidOrderException, OrderNotFoundException
from app.paper.schemas import (
    PaperAccountResponse,
    PaperFillResponse,
    PaperOrderCreateRequest,
    PaperOrderResponse,
    PaperPositionResponse,
    RiskStatusResponse,
)


class PaperService:
    """
    High-level application service for paper trading operations.
    """

    def __init__(self, broker: Optional[PaperBroker] = None):
        self.broker = broker or PaperBroker()
        self.market_service = MarketDataService()

    async def get_latest_market_candle(
        self,
        db: AsyncSession,
        symbol: str = "BTCUSDT",
        interval: str = "1m",
    ) -> Optional[MarketCandle]:
        """
        Retrieves the most recent closed market candle from the database.
        """
        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.interval == interval,
                MarketCandle.is_closed.is_(True),
            )
            .order_by(MarketCandle.open_time.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def submit_paper_order(
        self,
        db: AsyncSession,
        request: PaperOrderCreateRequest,
    ) -> PaperOrderResponse:
        """
        Submits order through the Central Risk Gate and PaperBroker.
        Fetches latest market data from the database if current_market_price is not provided.
        """
        candle = await self.get_latest_market_candle(db, symbol=request.symbol)

        market_price = request.current_market_price
        feed_time = None
        bar_vol = None

        if candle:
            if market_price is None or market_price <= 0:
                market_price = candle.close
            feed_time = candle.open_time
            bar_vol = candle.volume
        elif market_price is None or market_price <= 0:
            # If no candle and no price provided, reject with helpful instruction
            raise InvalidOrderException(
                f"No market data found for {request.symbol} and no reference price supplied. Ingest market candles first."
            )

        order = await self.broker.submit_order(
            db=db,
            request=request,
            current_market_price=market_price,
            latest_feed_time=feed_time,
            bar_volume=bar_vol,
        )

        return self._to_order_response(order)

    async def get_account_overview(
        self,
        db: AsyncSession,
        symbol: str = "BTCUSDT",
    ) -> PaperAccountResponse:
        """
        Returns complete account overview with positions valued at current mark price.
        """
        account = await self.broker.get_or_create_default_account(db)
        candle = await self.get_latest_market_candle(db, symbol=symbol)
        mark_price = candle.close if candle else 50000.0

        # Query positions
        stmt = select(PaperPosition).where(PaperPosition.account_id == account.id)
        positions = (await db.execute(stmt)).scalars().all()

        pos_responses: List[PaperPositionResponse] = []
        total_positions_val = 0.0
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0

        for p in positions:
            p_val = p.quantity * mark_price
            p_unrealized = (mark_price - p.avg_entry_price) * p.quantity if p.quantity > 0 else 0.0
            p_unrealized_pct = (p_unrealized / p.cost_basis * 100.0) if p.cost_basis > 0 else 0.0

            pos_responses.append(
                PaperPositionResponse(
                    symbol=p.symbol,
                    quantity=p.quantity,
                    avg_entry_price=p.avg_entry_price,
                    cost_basis=p.cost_basis,
                    current_price=mark_price,
                    market_value=p_val,
                    unrealized_pnl=p_unrealized,
                    unrealized_pnl_pct=p_unrealized_pct,
                    realized_pnl=p.realized_pnl,
                )
            )
            total_positions_val += p_val
            total_unrealized_pnl += p_unrealized
            total_realized_pnl += p.realized_pnl

        total_equity = account.virtual_balance + total_positions_val

        return PaperAccountResponse(
            account_id=account.id,
            name=account.name,
            virtual_balance=account.virtual_balance,
            currency=account.currency,
            total_positions_value=total_positions_val,
            total_equity=total_equity,
            unrealized_pnl=total_unrealized_pnl,
            realized_pnl=total_realized_pnl,
            positions=pos_responses,
            is_active=account.is_active,
            created_at=account.created_at,
        )

    async def list_orders(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[PaperOrderResponse]:
        """
        Lists paper orders with optional filtering.
        """
        account = await self.broker.get_or_create_default_account(db)
        query = select(PaperOrder).where(PaperOrder.account_id == account.id)

        if status:
            query = query.where(PaperOrder.status == status)
        if symbol:
            query = query.where(PaperOrder.symbol == symbol)

        query = query.order_by(PaperOrder.created_at.desc()).limit(limit)
        orders = (await db.execute(query)).scalars().all()
        return [self._to_order_response(o) for o in orders]

    async def get_order_details(self, db: AsyncSession, order_id: str) -> Tuple[PaperOrderResponse, List[PaperFillResponse]]:
        """
        Fetches single order and its associated execution fills.
        """
        stmt = select(PaperOrder).where(PaperOrder.id == order_id)
        order = (await db.execute(stmt)).scalars().first()
        if not order:
            raise OrderNotFoundException(f"Paper order '{order_id}' not found.")

        fill_stmt = select(PaperFill).where(PaperFill.order_id == order.id).order_by(PaperFill.created_at.asc())
        fills = (await db.execute(fill_stmt)).scalars().all()

        fill_responses = [
            PaperFillResponse(
                id=f.id,
                order_id=f.order_id,
                symbol=f.symbol,
                side=f.side,
                fill_price=f.fill_price,
                quantity=f.quantity,
                gross_notional=f.gross_notional,
                fee=f.fee,
                slippage_cost=f.slippage_cost,
                realized_pnl=f.realized_pnl,
                created_at=f.created_at,
            )
            for f in fills
        ]

        return self._to_order_response(order), fill_responses

    async def cancel_paper_order(self, db: AsyncSession, order_id: str) -> PaperOrderResponse:
        """
        Cancels an open limit order.
        """
        order = await self.broker.cancel_order(db, order_id)
        return self._to_order_response(order)

    async def get_risk_status(self, db: AsyncSession, symbol: str = "BTCUSDT") -> RiskStatusResponse:
        """
        Returns full Central Risk Gate metrics, current limits, feed status, and emergency stop state.
        """
        account = await self.broker.get_or_create_default_account(db)
        risk_state = await self.broker.get_account_risk_state(db, account.id)
        candle = await self.get_latest_market_candle(db, symbol=symbol)

        now_utc = datetime.now(timezone.utc)
        feed_status = "UNKNOWN"
        feed_time = None
        if candle:
            feed_time = candle.open_time
            if feed_time.tzinfo is None:
                feed_time = feed_time.replace(tzinfo=timezone.utc)
            age = (now_utc - feed_time).total_seconds()
            feed_status = "HEALTHY" if age <= DEFAULT_MAX_FEED_AGE_SECONDS else "STALE"

        # Calculate current drawdown %
        current_equity = account.virtual_balance
        pos = await self.broker.get_position(db, account.id, symbol)
        if pos and candle:
            current_equity += pos.quantity * candle.close

        current_dd_pct = 0.0
        if risk_state.peak_equity > 0:
            current_dd_pct = max(0.0, (risk_state.peak_equity - current_equity) / risk_state.peak_equity * 100.0)

        is_trading_allowed = not risk_state.emergency_stop and feed_status == "HEALTHY"

        return RiskStatusResponse(
            emergency_stop=risk_state.emergency_stop,
            kill_switch_reason=risk_state.kill_switch_reason,
            max_order_notional=risk_state.max_order_notional,
            max_position_pct=risk_state.max_position_pct * 100.0,
            max_portfolio_exposure_pct=risk_state.max_portfolio_exposure_pct * 100.0,
            daily_loss_limit_pct=risk_state.daily_loss_limit_pct * 100.0,
            max_drawdown_limit_pct=risk_state.max_drawdown_limit_pct * 100.0,
            consecutive_loss_limit=risk_state.consecutive_loss_limit,
            starting_daily_equity=risk_state.starting_daily_equity,
            current_daily_pnl=risk_state.current_daily_pnl,
            peak_equity=risk_state.peak_equity,
            current_drawdown_pct=current_dd_pct,
            consecutive_losses=risk_state.consecutive_losses,
            last_breach_reason=risk_state.last_breach_reason,
            feed_status=feed_status,
            last_feed_time=feed_time,
            is_trading_allowed=is_trading_allowed,
        )

    async def trigger_emergency_stop(self, db: AsyncSession, reason: str) -> RiskStatusResponse:
        await self.broker.trigger_emergency_stop(db, reason)
        return await self.get_risk_status(db)

    async def resume_emergency_stop(
        self,
        db: AsyncSession,
        confirmation: str,
        reset_consecutive_losses: bool = False,
    ) -> RiskStatusResponse:
        await self.broker.resume_emergency_stop(db, confirmation, reset_consecutive_losses)
        return await self.get_risk_status(db)

    async def match_market_price(
        self,
        db: AsyncSession,
        symbol: str,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        volume: Optional[float] = None,
    ) -> List[PaperFillResponse]:
        """
        Feeds new market price to match open limit orders and returns executed fills.
        """
        high_price = high if high is not None else price
        low_price = low if low is not None else price

        fills = await self.broker.match_open_orders(
            db=db,
            symbol=symbol,
            high_price=high_price,
            low_price=low_price,
            close_price=price,
            volume=volume,
        )

        return [
            PaperFillResponse(
                id=f.id,
                order_id=f.order_id,
                symbol=f.symbol,
                side=f.side,
                fill_price=f.fill_price,
                quantity=f.quantity,
                gross_notional=f.gross_notional,
                fee=f.fee,
                slippage_cost=f.slippage_cost,
                realized_pnl=f.realized_pnl,
                created_at=f.created_at,
            )
            for f in fills
        ]

    def _to_order_response(self, order: PaperOrder) -> PaperOrderResponse:
        return PaperOrderResponse(
            id=order.id,
            client_order_id=order.client_order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            status=order.status,
            fee=order.fee,
            slippage_cost=order.slippage_cost,
            rejection_reason=order.rejection_reason,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
