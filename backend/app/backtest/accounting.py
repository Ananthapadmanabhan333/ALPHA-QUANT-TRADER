from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.backtest.constants import OrderSide


@dataclass
class TradeRecord:
    trade_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: OrderSide
    fill_price: float
    quantity: float
    gross_notional: float
    fee: float
    slippage_cost: float
    realized_gross_pnl: float
    realized_net_pnl: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "fill_price": self.fill_price,
            "quantity": self.quantity,
            "gross_notional": self.gross_notional,
            "fee": self.fee,
            "slippage_cost": self.slippage_cost,
            "realized_gross_pnl": self.realized_gross_pnl,
            "realized_net_pnl": self.realized_net_pnl,
        }


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    total_cost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.quantity > 1e-8

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        if not self.is_open:
            return 0.0
        return self.quantity * (current_price - self.avg_entry_price)


@dataclass
class EquitySnapshot:
    timestamp: datetime
    cash: float
    positions_value: float
    total_equity: float
    gross_pnl: float
    net_pnl: float
    cumulative_fees: float
    cumulative_slippage: float
    drawdown_pct: float
    in_position: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cash": round(self.cash, 4),
            "positions_value": round(self.positions_value, 4),
            "total_equity": round(self.total_equity, 4),
            "gross_pnl": round(self.gross_pnl, 4),
            "net_pnl": round(self.net_pnl, 4),
            "cumulative_fees": round(self.cumulative_fees, 4),
            "cumulative_slippage": round(self.cumulative_slippage, 4),
            "drawdown_pct": round(self.drawdown_pct, 4),
            "in_position": self.in_position,
        }


class PortfolioLedger:
    """
    Fixed-precision portfolio accounting ledger.
    Guarantees mathematical accounting invariants:
    - Equity_t = Cash_t + sum(PositionsValue_t)
    - Net P&L = Gross P&L - Cumulative Fees - Cumulative Slippage
    """

    def __init__(self, initial_cash: float = 10000.0):
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[EquitySnapshot] = []

        # Running accounting totals
        self.cumulative_fees: float = 0.0
        self.cumulative_slippage: float = 0.0
        self.realized_gross_pnl: float = 0.0
        self.peak_equity: float = float(initial_cash)

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def record_buy(
        self,
        trade_id: str,
        order_id: str,
        timestamp: datetime,
        symbol: str,
        fill_price: float,
        quantity: float,
        fee: float,
        slippage_cost: float,
    ) -> TradeRecord:
        gross_notional = fill_price * quantity
        total_deduction = gross_notional + fee

        if total_deduction > (self.cash + 1e-6):
            raise ValueError(
                f"Insufficient cash for buy fill: needed {total_deduction:.2f}, available {self.cash:.2f}"
            )

        self.cash -= total_deduction
        self.cumulative_fees += fee
        self.cumulative_slippage += (slippage_cost * quantity)

        pos = self.get_position(symbol)
        new_qty = pos.quantity + quantity
        pos.total_cost += gross_notional
        pos.avg_entry_price = pos.total_cost / new_qty if new_qty > 0 else 0.0
        pos.quantity = new_qty

        trade = TradeRecord(
            trade_id=trade_id,
            order_id=order_id,
            timestamp=timestamp,
            symbol=symbol,
            side=OrderSide.BUY,
            fill_price=fill_price,
            quantity=quantity,
            gross_notional=gross_notional,
            fee=fee,
            slippage_cost=slippage_cost * quantity,
            realized_gross_pnl=0.0,
            realized_net_pnl=-fee - (slippage_cost * quantity),
        )
        self.trades.append(trade)
        return trade

    def record_sell(
        self,
        trade_id: str,
        order_id: str,
        timestamp: datetime,
        symbol: str,
        fill_price: float,
        quantity: float,
        fee: float,
        slippage_cost: float,
    ) -> TradeRecord:
        pos = self.get_position(symbol)
        if quantity > (pos.quantity + 1e-8):
            raise ValueError(
                f"Cannot sell more than held position: requested {quantity:.6f}, available {pos.quantity:.6f}"
            )

        gross_notional = fill_price * quantity
        net_proceeds = gross_notional - fee

        self.cash += net_proceeds
        self.cumulative_fees += fee
        self.cumulative_slippage += (slippage_cost * quantity)

        # Realized P&L calculation
        cost_basis_fraction = pos.avg_entry_price * quantity
        realized_gross = gross_notional - cost_basis_fraction
        realized_net = realized_gross - fee - (slippage_cost * quantity)

        self.realized_gross_pnl += realized_gross

        pos.quantity -= quantity
        pos.total_cost -= cost_basis_fraction
        if pos.quantity <= 1e-8:
            pos.quantity = 0.0
            pos.total_cost = 0.0
            pos.avg_entry_price = 0.0

        trade = TradeRecord(
            trade_id=trade_id,
            order_id=order_id,
            timestamp=timestamp,
            symbol=symbol,
            side=OrderSide.SELL,
            fill_price=fill_price,
            quantity=quantity,
            gross_notional=gross_notional,
            fee=fee,
            slippage_cost=slippage_cost * quantity,
            realized_gross_pnl=realized_gross,
            realized_net_pnl=realized_net,
        )
        self.trades.append(trade)
        return trade

    def record_bar_snapshot(self, timestamp: datetime, current_prices: Dict[str, float]) -> EquitySnapshot:
        """Records end-of-bar equity, unrealized P&L, fees, and drawdown."""
        positions_value = sum(
            pos.market_value(current_prices.get(symbol, pos.avg_entry_price))
            for symbol, pos in self.positions.items()
        )
        total_equity = self.cash + positions_value

        if total_equity > self.peak_equity:
            self.peak_equity = total_equity

        drawdown_pct = 0.0
        if self.peak_equity > 0:
            drawdown_pct = max(0.0, (self.peak_equity - total_equity) / self.peak_equity * 100.0)

        unrealized = sum(
            pos.unrealized_pnl(current_prices.get(symbol, pos.avg_entry_price))
            for symbol, pos in self.positions.items()
        )
        gross_pnl = self.realized_gross_pnl + unrealized
        net_pnl = total_equity - self.initial_cash

        in_pos = any(pos.is_open for pos in self.positions.values())

        snapshot = EquitySnapshot(
            timestamp=timestamp,
            cash=self.cash,
            positions_value=positions_value,
            total_equity=total_equity,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            cumulative_fees=self.cumulative_fees,
            cumulative_slippage=self.cumulative_slippage,
            drawdown_pct=drawdown_pct,
            in_position=in_pos,
        )
        self.equity_curve.append(snapshot)
        return snapshot
