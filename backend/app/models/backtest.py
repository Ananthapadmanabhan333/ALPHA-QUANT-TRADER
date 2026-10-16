from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BacktestRun(Base):
    """
    Persisted backtesting run record storing strategy configuration,
    cryptographic dataset fingerprint, execution cost model assumptions,
    equity curve timeseries, and statistical performance metrics.
    """
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    config_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(10), nullable=False)

    time_range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    candle_count: Mapped[int] = mapped_column(Integer, nullable=False)

    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    cost_assumptions: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed", index=True)

    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    equity_curve: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)

    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_return_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_backtest_runs_lookup", "strategy_id", "symbol", "created_at"),
        Index("ix_backtest_runs_fingerprint", "dataset_fingerprint"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestRun(id='{self.id}', strategy='{self.strategy_id}', "
            f"symbol='{self.symbol}', net_ret={self.net_return_pct:.2f}%)>"
        )


class BacktestTradeLog(Base):
    """
    Persisted trade fill ledger generated during backtesting simulation.
    """
    __tablename__ = "backtest_trades"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    backtest_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    gross_notional: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_cost: Mapped[float] = mapped_column(Float, nullable=False)
    realized_net_pnl: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_backtest_trades_run_ts", "backtest_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestTradeLog(backtest='{self.backtest_id}', side='{self.side}', "
            f"fill={self.fill_price:.2f}, net_pnl={self.realized_net_pnl:.2f})>"
        )
