"""
ALPHA Quant — Phase 5: Paper Trading Application Service.
Orchestrates PaperBroker, MarketData feeds, risk evaluations, and read queries.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.service import MarketDataService
from app.models.market import MarketCandle
from app.models.paper import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperRiskEvent,
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
        Retrieves the most recent market candle (including live streaming tick) from the database.
        """
        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.interval == interval,
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

    async def list_orders_paginated(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[int, List[PaperOrderResponse]]:
        """Returns total matching order count and paginated list of orders."""
        query = select(PaperOrder)
        count_query = select(func.count(PaperOrder.id))

        if status:
            query = query.where(PaperOrder.status == status.lower())
            count_query = count_query.where(PaperOrder.status == status.lower())
        if symbol:
            norm_symbol = symbol.replace("/", "").upper()
            query = query.where(PaperOrder.symbol == norm_symbol)
            count_query = count_query.where(PaperOrder.symbol == norm_symbol)
        if side:
            query = query.where(PaperOrder.side == side.lower())
            count_query = count_query.where(PaperOrder.side == side.lower())

        total = (await db.execute(count_query)).scalar() or 0
        stmt = query.order_by(PaperOrder.created_at.desc()).limit(limit).offset(offset)
        orders = (await db.execute(stmt)).scalars().all()
        return total, [self._to_order_response(o) for o in orders]

    async def list_fills_paginated(
        self,
        db: AsyncSession,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        order_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[int, List[PaperFillResponse]]:
        """Returns total matching fill count and paginated list of fills."""
        query = select(PaperFill)
        count_query = select(func.count(PaperFill.id))

        if symbol:
            norm_symbol = symbol.replace("/", "").upper()
            query = query.where(PaperFill.symbol == norm_symbol)
            count_query = count_query.where(PaperFill.symbol == norm_symbol)
        if side:
            query = query.where(PaperFill.side == side.lower())
            count_query = count_query.where(PaperFill.side == side.lower())
        if order_id:
            query = query.where(PaperFill.order_id == order_id)
            count_query = count_query.where(PaperFill.order_id == order_id)

        total = (await db.execute(count_query)).scalar() or 0
        stmt = query.order_by(PaperFill.created_at.desc()).limit(limit).offset(offset)
        fills = (await db.execute(stmt)).scalars().all()

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
        return total, fill_responses

    async def list_events_paginated(
        self,
        db: AsyncSession,
        severity: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[int, List[dict]]:
        """Returns total count and paginated list of system/risk/lifecycle events."""
        query = select(PaperRiskEvent)
        count_query = select(func.count(PaperRiskEvent.id))

        if severity:
            query = query.where(PaperRiskEvent.severity == severity.upper())
            count_query = count_query.where(PaperRiskEvent.severity == severity.upper())
        if event_type:
            query = query.where(PaperRiskEvent.event_type == event_type.upper())
            count_query = count_query.where(PaperRiskEvent.event_type == event_type.upper())

        total = (await db.execute(count_query)).scalar() or 0
        stmt = query.order_by(PaperRiskEvent.created_at.desc()).limit(limit).offset(offset)
        events = (await db.execute(stmt)).scalars().all()

        items = [
            {
                "id": e.id,
                "account_id": e.account_id,
                "event_type": e.event_type,
                "severity": e.severity,
                "reason": e.reason,
                "metadata_json": e.metadata_json or {},
                "created_at": e.created_at,
            }
            for e in events
        ]
        return total, items

    async def reset_risk_limits(
        self,
        db: AsyncSession,
        confirmation_code: str,
        reset_emergency_stop: bool = True,
        reset_consecutive_losses: bool = True,
        reset_daily_loss: bool = False,
        reason: Optional[str] = None,
    ) -> RiskStatusResponse:
        """
        Operator authorized reset of breached risk controls.
        Safety Invariant: Requires explicit 'CONFIRM_RESET' code and writes an immutable audit record.
        """
        if confirmation_code.strip() != "CONFIRM_RESET":
            raise InvalidOrderException("Invalid confirmation code. Must supply 'CONFIRM_RESET'.")

        account = await self.broker.get_or_create_default_account(db)
        risk_state = await self.broker.get_account_risk_state(db, account.id)

        actions_taken = []
        if reset_emergency_stop and risk_state.emergency_stop:
            risk_state.emergency_stop = False
            risk_state.kill_switch_reason = None
            actions_taken.append("emergency_stop_cleared")

        if reset_consecutive_losses and risk_state.consecutive_losses > 0:
            risk_state.consecutive_losses = 0
            actions_taken.append("consecutive_losses_reset")

        if reset_daily_loss:
            risk_state.current_daily_pnl = 0.0
            actions_taken.append("daily_loss_reset")

        # Persist audit event
        audit_reason = reason or "Operator manual risk reset applied"
        audit_event = PaperRiskEvent(
            id=str(uuid.uuid4()),
            account_id=account.id,
            event_type="RISK_RESET",
            severity="WARNING",
            reason=f"{audit_reason}: {', '.join(actions_taken) if actions_taken else 'no_changes'}",
            metadata_json={
                "actions": actions_taken,
                "reset_emergency_stop": reset_emergency_stop,
                "reset_consecutive_losses": reset_consecutive_losses,
                "reset_daily_loss": reset_daily_loss,
            },
        )
        db.add(audit_event)
        await db.commit()

        return await self.get_risk_status(db)

    async def reset_paper_account(
        self,
        db: AsyncSession,
        initial_cash: float = 10000.0,
        clear_history: bool = True,
    ) -> PaperAccountResponse:
        """
        Resets the virtual paper trading account to a specified starting capital,
        flattens simulated positions, resets risk state counters, and optionally clears order history.
        """
        account = await self.broker.get_or_create_default_account(db)
        risk_state = await self.broker.get_account_risk_state(db, account.id)

        # Clear open positions
        await db.execute(delete(PaperPosition).where(PaperPosition.account_id == account.id))

        if clear_history:
            await db.execute(delete(PaperFill))
            await db.execute(delete(PaperOrder).where(PaperOrder.account_id == account.id))

        account.virtual_balance = float(initial_cash)

        # Reset risk state baselines to match new virtual equity
        risk_state.emergency_stop = False
        risk_state.kill_switch_reason = None
        risk_state.starting_daily_equity = float(initial_cash)
        risk_state.current_daily_pnl = 0.0
        risk_state.peak_equity = float(initial_cash)
        risk_state.consecutive_losses = 0
        risk_state.last_breach_reason = None

        audit_event = PaperRiskEvent(
            id=str(uuid.uuid4()),
            account_id=account.id,
            event_type="ACCOUNT_CAPITAL_RESET",
            severity="INFO",
            reason=f"Virtual paper account reset to ${initial_cash:,.2f} USDT (clear_history={clear_history})",
            metadata_json={"initial_cash": initial_cash, "clear_history": clear_history},
        )
        db.add(audit_event)
        await db.commit()

        return await self.get_account_overview(db)

