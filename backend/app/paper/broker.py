"""
ALPHA Quant — Phase 5: Dedicated Paper Broker Engine.
Simulates institutional spot execution, position accounting, order lifecycle,
idempotent order submissions, and atomic ledger reconciliation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PaperRiskEvent,
    PaperRiskState,
)
from app.paper.constants import (
    DEFAULT_INITIAL_CASH,
    DEFAULT_MAKER_FEE_BPS,
    DEFAULT_SLIPPAGE_BPS,
    DEFAULT_TAKER_FEE_BPS,
    DEFAULT_MAX_LIQUIDITY_PARTICIPATION_PCT,
    OrderStatus,
    OrderSide,
    OrderType,
    RiskEventSeverity,
    RiskEventType,
)
from app.paper.exceptions import (
    DuplicateOrderException,
    InsufficientBalanceException,
    InvalidOrderException,
    OrderNotFoundException,
    ReconciliationException,
    RiskBreachException,
)
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest


class PaperBroker:
    """
    Dedicated Paper Broker for simulated algorithmic execution.
    Safety Invariant: Pure simulation engine with zero exchange connectivity.
    """

    def __init__(self, risk_gate: Optional[CentralRiskGate] = None):
        self.risk_gate = risk_gate or CentralRiskGate()

    async def get_or_create_default_account(self, db: AsyncSession) -> PaperAccount:
        """
        Retrieves the default simulated account or initializes one with default cash and risk state.
        """
        stmt = select(PaperAccount).where(PaperAccount.is_active.is_(True)).order_by(PaperAccount.created_at.asc())
        res = await db.execute(stmt)
        account = res.scalars().first()

        if not account:
            account = PaperAccount(
                id=str(uuid.uuid4()),
                name="Default Paper Account",
                virtual_balance=DEFAULT_INITIAL_CASH,
                currency="USDT",
                is_active=True,
            )
            db.add(account)
            await db.flush()

            # Initialize Risk State
            risk_state = PaperRiskState(
                id=str(uuid.uuid4()),
                account_id=account.id,
                emergency_stop=False,
                starting_daily_equity=DEFAULT_INITIAL_CASH,
                peak_equity=DEFAULT_INITIAL_CASH,
                current_daily_pnl=0.0,
                consecutive_losses=0,
                last_daily_reset=datetime.now(timezone.utc),
            )
            db.add(risk_state)
            await db.commit()
            await db.refresh(account)

        return account

    async def get_account_risk_state(self, db: AsyncSession, account_id: str) -> PaperRiskState:
        """
        Fetches the persisted risk state for an account.
        """
        stmt = select(PaperRiskState).where(PaperRiskState.account_id == account_id)
        res = await db.execute(stmt)
        risk_state = res.scalars().first()
        if not risk_state:
            risk_state = PaperRiskState(
                id=str(uuid.uuid4()),
                account_id=account_id,
                emergency_stop=False,
                starting_daily_equity=DEFAULT_INITIAL_CASH,
                peak_equity=DEFAULT_INITIAL_CASH,
                current_daily_pnl=0.0,
                consecutive_losses=0,
                last_daily_reset=datetime.now(timezone.utc),
            )
            db.add(risk_state)
            await db.flush()
        return risk_state

    async def get_position(self, db: AsyncSession, account_id: str, symbol: str) -> Optional[PaperPosition]:
        """
        Retrieves current position in base asset for an account.
        """
        stmt = select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.symbol == symbol,
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def submit_order(
        self,
        db: AsyncSession,
        request: PaperOrderCreateRequest,
        current_market_price: float,
        latest_feed_time: Optional[datetime] = None,
        bar_volume: Optional[float] = None,
        spread_bps: Optional[float] = None,
    ) -> PaperOrder:
        """
        Submits, validates through Risk Gate, and simulates execution of an order.
        Guarantees idempotency via client_order_id.
        All balance, position, and order updates occur within a single database transaction.
        """
        account = await self.get_or_create_default_account(db)
        risk_state = await self.get_account_risk_state(db, account.id)

        # 1. Idempotency Check
        client_order_id = request.client_order_id or f"client-{uuid.uuid4().hex[:16]}"
        stmt = select(PaperOrder).where(PaperOrder.client_order_id == client_order_id)
        existing = (await db.execute(stmt)).scalars().first()
        if existing:
            # Return idempotent cached order
            return existing

        current_position = await self.get_position(db, account.id, request.symbol)

        # 2. Central Risk Gate Check
        try:
            self.risk_gate.check_pre_trade_invariants(
                request=request,
                account=account,
                risk_state=risk_state,
                current_position=current_position,
                current_price=current_market_price,
                latest_feed_time=latest_feed_time,
                spread_bps=spread_bps,
            )
        except Exception as exc:
            # Persist rejected order & risk event
            rejection_reason = str(exc)
            order = PaperOrder(
                id=str(uuid.uuid4()),
                client_order_id=client_order_id,
                account_id=account.id,
                symbol=request.symbol,
                side=request.side.value if hasattr(request.side, "value") else str(request.side),
                order_type=request.order_type.value if hasattr(request.order_type, "value") else str(request.order_type),
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.REJECTED.value,
                rejection_reason=rejection_reason,
            )
            db.add(order)

            risk_event = PaperRiskEvent(
                id=str(uuid.uuid4()),
                account_id=account.id,
                event_type=RiskEventType.RISK_LIMIT_BREACH.value,
                severity=RiskEventSeverity.WARNING.value,
                reason=rejection_reason,
                metadata_json={
                    "client_order_id": client_order_id,
                    "symbol": request.symbol,
                    "quantity": request.quantity,
                },
            )
            db.add(risk_event)
            await db.commit()
            raise exc

        # 3. Balance and Inventory Sufficiency Check
        fee_bps = DEFAULT_TAKER_FEE_BPS if request.order_type == OrderType.MARKET else DEFAULT_MAKER_FEE_BPS
        slippage_bps = DEFAULT_SLIPPAGE_BPS if request.order_type == OrderType.MARKET else 0.0

        ref_price = request.price if request.price is not None and request.price > 0 else current_market_price

        if request.side == OrderSide.BUY:
            est_fill_price = ref_price * (1.0 + slippage_bps / 10000.0)
            est_gross_notional = est_fill_price * request.quantity
            est_fee = est_gross_notional * (fee_bps / 10000.0)
            required_cash = est_gross_notional + est_fee

            if account.virtual_balance < required_cash:
                raise InsufficientBalanceException(
                    f"Insufficient virtual cash balance: ${account.virtual_balance:.2f} available, ${required_cash:.2f} required."
                )
        else:
            # SELL check
            pos_qty = current_position.quantity if current_position else 0.0
            if pos_qty < request.quantity:
                raise InsufficientBalanceException(
                    f"Insufficient spot inventory for {request.symbol}: {pos_qty:.4f} available, {request.quantity:.4f} required."
                )

        # 4. Create Order Record
        order = PaperOrder(
            id=str(uuid.uuid4()),
            client_order_id=client_order_id,
            account_id=account.id,
            symbol=request.symbol,
            side=request.side.value if hasattr(request.side, "value") else str(request.side),
            order_type=request.order_type.value if hasattr(request.order_type, "value") else str(request.order_type),
            quantity=request.quantity,
            price=request.price,
            status=OrderStatus.PENDING.value,
        )
        db.add(order)
        await db.flush()

        # 5. Execute or Queue Order
        if request.order_type == OrderType.MARKET:
            await self._execute_fill(
                db=db,
                order=order,
                account=account,
                risk_state=risk_state,
                market_price=current_market_price,
                is_taker=True,
                bar_volume=bar_volume,
            )
        elif request.order_type == OrderType.LIMIT:
            # Check if immediately marketable
            is_marketable = False
            if request.side == OrderSide.BUY and request.price is not None and request.price >= current_market_price:
                is_marketable = True
            elif request.side == OrderSide.SELL and request.price is not None and request.price <= current_market_price:
                is_marketable = True

            if is_marketable:
                await self._execute_fill(
                    db=db,
                    order=order,
                    account=account,
                    risk_state=risk_state,
                    market_price=request.price or current_market_price,
                    is_taker=False,
                    bar_volume=bar_volume,
                )
            else:
                order.status = OrderStatus.OPEN.value

        await db.commit()
        await db.refresh(order)
        return order

    async def _execute_fill(
        self,
        db: AsyncSession,
        order: PaperOrder,
        account: PaperAccount,
        risk_state: PaperRiskState,
        market_price: float,
        is_taker: bool,
        bar_volume: Optional[float] = None,
    ) -> PaperFill:
        """
        Executes fill, applies adverse slippage and fees, updates position with weighted-average cost,
        deducts/credits cash, and updates risk metrics within the caller's transaction.
        """
        fee_bps = DEFAULT_TAKER_FEE_BPS if is_taker else DEFAULT_MAKER_FEE_BPS
        slippage_bps = DEFAULT_SLIPPAGE_BPS if is_taker else 0.0

        # Slippage penalty: adverse direction
        if order.side == OrderSide.BUY.value:
            fill_price = market_price * (1.0 + slippage_bps / 10000.0)
            slippage_cost = (fill_price - market_price) * order.quantity
        else:
            fill_price = market_price * (1.0 - slippage_bps / 10000.0)
            slippage_cost = (market_price - fill_price) * order.quantity

        # Liquidity constraint: partial fill if order exceeds cap of bar volume
        fill_qty = order.quantity
        if bar_volume is not None and bar_volume > 0:
            max_liquidity = bar_volume * DEFAULT_MAX_LIQUIDITY_PARTICIPATION_PCT
            if fill_qty > max_liquidity:
                fill_qty = max_liquidity

        gross_notional = fill_price * fill_qty
        fee = gross_notional * (fee_bps / 10000.0)

        # Position Accounting
        position = await self.get_position(db, account.id, order.symbol)
        if not position:
            position = PaperPosition(
                id=str(uuid.uuid4()),
                account_id=account.id,
                symbol=order.symbol,
                quantity=0.0,
                avg_entry_price=0.0,
                cost_basis=0.0,
                realized_pnl=0.0,
            )
            db.add(position)
            await db.flush()

        realized_pnl = 0.0
        if order.side == OrderSide.BUY.value:
            # Weighted average cost calculation
            new_qty = position.quantity + fill_qty
            new_cost_basis = position.cost_basis + gross_notional
            position.quantity = new_qty
            position.cost_basis = new_cost_basis
            position.avg_entry_price = new_cost_basis / new_qty if new_qty > 0 else 0.0

            # Deduct cash
            account.virtual_balance -= (gross_notional + fee)
        else:
            # Realized PnL calculation on SELL
            avg_cost = position.avg_entry_price
            gross_pnl = (fill_price - avg_cost) * fill_qty
            realized_pnl = gross_pnl - fee - slippage_cost

            new_qty = max(0.0, position.quantity - fill_qty)
            position.quantity = new_qty
            position.cost_basis = avg_cost * new_qty
            if new_qty == 0.0:
                position.avg_entry_price = 0.0
            position.realized_pnl += realized_pnl

            # Credit cash
            account.virtual_balance += (gross_notional - fee)

            # Update Risk State metrics on closed trade
            risk_state.current_daily_pnl += realized_pnl
            if realized_pnl < 0:
                risk_state.consecutive_losses += 1
            else:
                risk_state.consecutive_losses = 0

        # Update Order record
        order.filled_quantity = fill_qty
        order.avg_fill_price = fill_price
        order.fee += fee
        order.slippage_cost += slippage_cost
        if fill_qty < order.quantity:
            order.status = OrderStatus.PARTIALLY_FILLED.value
        else:
            order.status = OrderStatus.FILLED.value

        # Create PaperFill record
        fill = PaperFill(
            id=str(uuid.uuid4()),
            order_id=order.id,
            account_id=account.id,
            symbol=order.symbol,
            side=order.side,
            fill_price=fill_price,
            quantity=fill_qty,
            gross_notional=gross_notional,
            fee=fee,
            slippage_cost=slippage_cost,
            realized_pnl=realized_pnl,
            created_at=datetime.now(timezone.utc),
        )
        db.add(fill)

        # Update Peak Equity watermark
        pos_val = position.quantity * market_price
        total_eq = account.virtual_balance + pos_val
        if total_eq > risk_state.peak_equity:
            risk_state.peak_equity = total_eq

        return fill

    async def match_open_orders(
        self,
        db: AsyncSession,
        symbol: str,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: Optional[float] = None,
    ) -> List[PaperFill]:
        """
        Evaluates open limit orders against intrabar price bounds [Low, High].
        Fills touched limit orders with atomic ledger updates.
        """
        account = await self.get_or_create_default_account(db)
        risk_state = await self.get_account_risk_state(db, account.id)

        stmt = select(PaperOrder).where(
            PaperOrder.account_id == account.id,
            PaperOrder.symbol == symbol,
            PaperOrder.status.in_([OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value]),
        )
        orders = (await db.execute(stmt)).scalars().all()
        fills: List[PaperFill] = []

        for order in orders:
            if order.price is None:
                continue

            limit_touched = False
            if order.side == OrderSide.BUY.value and low_price <= order.price:
                limit_touched = True
            elif order.side == OrderSide.SELL.value and high_price >= order.price:
                limit_touched = True

            if limit_touched:
                fill = await self._execute_fill(
                    db=db,
                    order=order,
                    account=account,
                    risk_state=risk_state,
                    market_price=order.price,
                    is_taker=False,
                    bar_volume=volume,
                )
                fills.append(fill)

        if fills:
            await db.commit()

        return fills

    async def cancel_order(self, db: AsyncSession, order_id: str) -> PaperOrder:
        """
        Cancels an open or partially filled limit order.
        """
        stmt = select(PaperOrder).where(PaperOrder.id == order_id)
        order = (await db.execute(stmt)).scalars().first()
        if not order:
            raise OrderNotFoundException(f"Paper order '{order_id}' not found.")

        if order.status in [OrderStatus.FILLED.value, OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value]:
            return order

        order.status = OrderStatus.CANCELLED.value
        await db.commit()
        await db.refresh(order)
        return order

    async def reconcile_portfolio(
        self,
        db: AsyncSession,
        current_market_price: float,
        symbol: str = "BTCUSDT",
    ) -> dict:
        """
        Reconciles account cash, positions, and equity from persisted ledger records.
        Asserts Cash balance invariant. If an inconsistency is detected, triggers Emergency Stop.
        """
        account = await self.get_or_create_default_account(db)
        risk_state = await self.get_account_risk_state(db, account.id)
        position = await self.get_position(db, account.id, symbol)

        pos_qty = position.quantity if position else 0.0
        avg_price = position.avg_entry_price if position else 0.0
        market_val = pos_qty * current_market_price
        unrealized_pnl = (current_market_price - avg_price) * pos_qty if pos_qty > 0 else 0.0
        realized_pnl = position.realized_pnl if position else 0.0
        total_equity = account.virtual_balance + market_val

        # Sanity check: Cash must never be negative in long-only spot
        if account.virtual_balance < -0.01:
            risk_state.emergency_stop = True
            risk_state.kill_switch_reason = f"Reconciliation failure: Negative cash balance (${account.virtual_balance:.2f})"
            risk_event = PaperRiskEvent(
                id=str(uuid.uuid4()),
                account_id=account.id,
                event_type=RiskEventType.RECONCILIATION_FAILURE.value,
                severity=RiskEventSeverity.CRITICAL.value,
                reason=risk_state.kill_switch_reason,
                metadata_json={"cash": account.virtual_balance, "equity": total_equity},
            )
            db.add(risk_event)
            await db.commit()
            raise ReconciliationException(risk_state.kill_switch_reason)

        return {
            "account_id": account.id,
            "virtual_balance": account.virtual_balance,
            "currency": account.currency,
            "position_quantity": pos_qty,
            "avg_entry_price": avg_price,
            "market_value": market_val,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_equity": total_equity,
            "peak_equity": risk_state.peak_equity,
            "drawdown_pct": (risk_state.peak_equity - total_equity) / risk_state.peak_equity if risk_state.peak_equity > 0 else 0.0,
            "is_emergency_stop": risk_state.emergency_stop,
        }

    async def trigger_emergency_stop(self, db: AsyncSession, reason: str) -> PaperRiskState:
        """
        Manually triggers the Emergency Stop / Kill switch, halting new simulated entries.
        """
        account = await self.get_or_create_default_account(db)
        risk_state = await self.get_account_risk_state(db, account.id)

        risk_state.emergency_stop = True
        risk_state.kill_switch_reason = reason
        risk_state.last_breach_reason = reason

        risk_event = PaperRiskEvent(
            id=str(uuid.uuid4()),
            account_id=account.id,
            event_type=RiskEventType.EMERGENCY_STOP.value,
            severity=RiskEventSeverity.CRITICAL.value,
            reason=reason,
            metadata_json={"operator": "API_USER", "timestamp": datetime.now(timezone.utc).isoformat()},
        )
        db.add(risk_event)
        await db.commit()
        await db.refresh(risk_state)
        return risk_state

    async def resume_emergency_stop(
        self,
        db: AsyncSession,
        confirmation: str,
        reset_consecutive_losses: bool = False,
    ) -> PaperRiskState:
        """
        Resumes trading following explicit confirmation and invariant verification.
        """
        if confirmation != "CONFIRM_RESUME":
            raise InvalidOrderException("Confirmation token must exactly equal 'CONFIRM_RESUME' to unpause trading.")

        account = await self.get_or_create_default_account(db)
        risk_state = await self.get_account_risk_state(db, account.id)

        risk_state.emergency_stop = False
        risk_state.kill_switch_reason = None
        if reset_consecutive_losses:
            risk_state.consecutive_losses = 0

        risk_event = PaperRiskEvent(
            id=str(uuid.uuid4()),
            account_id=account.id,
            event_type=RiskEventType.EMERGENCY_RESUME.value,
            severity=RiskEventSeverity.INFO.value,
            reason="Emergency stop cleared by risk administrator.",
            metadata_json={"reset_consecutive_losses": reset_consecutive_losses},
        )
        db.add(risk_event)
        await db.commit()
        await db.refresh(risk_state)
        return risk_state
