from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from app.backtest.accounting import PortfolioLedger, TradeRecord
from app.backtest.constants import OrderSide, OrderStatus, OrderType
from app.backtest.cost_model import CostModel


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    requested_qty: float
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    fill_price: float = 0.0
    fee_paid: float = 0.0
    slippage_paid: float = 0.0
    created_at: Optional[datetime] = None
    execution_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    delay_remaining: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "order_type": self.order_type.value if hasattr(self.order_type, "value") else str(self.order_type),
            "requested_qty": self.requested_qty,
            "limit_price": self.limit_price,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "filled_qty": self.filled_qty,
            "fill_price": self.fill_price,
            "fee_paid": self.fee_paid,
            "slippage_paid": self.slippage_paid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "execution_time": self.execution_time.isoformat() if self.execution_time else None,
            "rejection_reason": self.rejection_reason,
        }


class SimulatedExecutionEngine:
    """
    Deterministic Event-Driven Simulated Execution Engine.

    Documented Fill Assumptions:
    1. Next-Bar Execution: Decisions generated at the close of candle t are queued
       and executed strictly against candle t+1 (never utilizing future prices).
    2. Market Order Fill: Executed at candle t+1 Open price, adjusted adversely by
       configured slippage and half-spread.
    3. Limit Order Fill: Fills at limit price if candle t+1 range (High/Low) touches
       or crosses limit price; maker fee schedule applied.
    4. Liquidity Constraint: Fill volume capped at max_volume_pct of candle volume.
    5. Order Validation: Rejects orders violating cash balance or position size.
    """

    def __init__(
        self,
        cost_model: CostModel,
        execution_delay_bars: int = 0,
        min_notional: float = 10.0,
    ):
        self.cost_model = cost_model
        self.execution_delay_bars = execution_delay_bars
        self.min_notional = min_notional
        self.pending_orders: List[Order] = []
        self.order_history: List[Order] = []

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        timestamp: datetime,
        limit_price: Optional[float] = None,
    ) -> Order:
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_qty=quantity,
            limit_price=limit_price,
            status=OrderStatus.PENDING,
            created_at=timestamp,
            delay_remaining=self.execution_delay_bars,
        )
        self.pending_orders.append(order)
        return order

    def process_next_bar_executions(
        self,
        candle: Dict[str, Any],
        ledger: PortfolioLedger,
    ) -> List[TradeRecord]:
        """
        Processes pending orders against the new eligible candle (t+1).
        Enforces strict next-bar execution and liquidity limits.
        """
        executed_trades: List[TradeRecord] = []
        remaining_pending: List[Order] = []

        bar_open_time = candle["open_time"]
        candle_open = float(candle["open"])
        candle_high = float(candle["high"])
        candle_low = float(candle["low"])
        candle_volume = float(candle["volume"])

        for order in self.pending_orders:
            # Check execution delay (e.g. latency simulation)
            if order.delay_remaining > 0:
                order.delay_remaining -= 1
                remaining_pending.append(order)
                continue

            # 1. Balance and Position Pre-Trade Validation
            if order.side == OrderSide.BUY:
                # Estimate cost at candle open
                est_fill_price, _ = self.cost_model.calculate_fill_price(
                    candle_open, OrderSide.BUY, is_maker=(order.order_type == OrderType.LIMIT)
                )
                est_notional = est_fill_price * order.requested_qty
                est_fee = self.cost_model.calculate_fee(est_notional, is_maker=False)

                if (est_notional + est_fee) > (ledger.cash + 1e-6):
                    # Check if we can afford a smaller fraction or reject
                    affordable_qty = (ledger.cash * 0.99) / (est_fill_price * 1.002)
                    if (affordable_qty * est_fill_price) < self.min_notional:
                        order.status = OrderStatus.REJECTED
                        order.rejection_reason = f"Insufficient cash: needed {est_notional:.2f}, available {ledger.cash:.2f}"
                        order.execution_time = bar_open_time
                        self.order_history.append(order)
                        continue
                    else:
                        order.requested_qty = affordable_qty

            elif order.side == OrderSide.SELL:
                pos = ledger.get_position(order.symbol)
                if not pos.is_open:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = f"No open position held for {order.symbol} to sell"
                    order.execution_time = bar_open_time
                    self.order_history.append(order)
                    continue
                # Cap sell quantity to held position
                if order.requested_qty > pos.quantity:
                    order.requested_qty = pos.quantity

            # 2. Check Order Type Fill Conditions
            can_fill = False
            ref_price = candle_open
            is_maker = False

            if order.order_type == OrderType.MARKET:
                can_fill = True
                ref_price = candle_open
                is_maker = False

            elif order.order_type == OrderType.LIMIT:
                if order.limit_price is None:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = "Limit order submitted without limit_price"
                    self.order_history.append(order)
                    continue

                if order.side == OrderSide.BUY:
                    # Buy limit fills if candle traded at or below limit
                    if candle_low <= order.limit_price:
                        can_fill = True
                        ref_price = order.limit_price
                        is_maker = True
                elif order.side == OrderSide.SELL:
                    # Sell limit fills if candle traded at or above limit
                    if candle_high >= order.limit_price:
                        can_fill = True
                        ref_price = order.limit_price
                        is_maker = True

            if not can_fill:
                # Remains pending for next eligible bar
                remaining_pending.append(order)
                continue

            # 3. Apply Liquidity Constraint
            fillable_qty, is_partial = self.cost_model.check_liquidity_constraint(
                order.requested_qty, candle_volume
            )

            if fillable_qty <= 0.0 or (fillable_qty * ref_price) < self.min_notional:
                order.status = OrderStatus.REJECTED
                order.rejection_reason = f"Liquidity constraint: bar volume {candle_volume:.2f} insufficient for min notional"
                order.execution_time = bar_open_time
                self.order_history.append(order)
                continue

            # 4. Calculate Execution Price & Deduct Costs
            fill_price, slip_unit = self.cost_model.calculate_fill_price(
                ref_price, order.side, is_maker=is_maker
            )
            gross_notional = fill_price * fillable_qty
            fee = self.cost_model.calculate_fee(gross_notional, is_maker=is_maker)

            # 5. Commit to Portfolio Ledger
            trade_id = str(uuid.uuid4())
            if order.side == OrderSide.BUY:
                trade = ledger.record_buy(
                    trade_id=trade_id,
                    order_id=order.order_id,
                    timestamp=bar_open_time,
                    symbol=order.symbol,
                    fill_price=fill_price,
                    quantity=fillable_qty,
                    fee=fee,
                    slippage_cost=slip_unit,
                )
            else:
                trade = ledger.record_sell(
                    trade_id=trade_id,
                    order_id=order.order_id,
                    timestamp=bar_open_time,
                    symbol=order.symbol,
                    fill_price=fill_price,
                    quantity=fillable_qty,
                    fee=fee,
                    slippage_cost=slip_unit,
                )

            executed_trades.append(trade)

            order.status = OrderStatus.PARTIALLY_FILLED if is_partial else OrderStatus.FILLED
            order.filled_qty = fillable_qty
            order.fill_price = fill_price
            order.fee_paid = fee
            order.slippage_paid = slip_unit * fillable_qty
            order.execution_time = bar_open_time
            self.order_history.append(order)

            # If partially filled, remaining quantity stays pending
            if is_partial and (order.requested_qty - fillable_qty) > 1e-6:
                order.requested_qty -= fillable_qty
                remaining_pending.append(order)

        self.pending_orders = remaining_pending
        return executed_trades
