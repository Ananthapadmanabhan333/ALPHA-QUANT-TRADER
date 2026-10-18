import math
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class BacktestCreateRequest(BaseModel):
    strategy_id: str
    strategy_version: str = Field(default="1.0.0")
    symbol: str = Field(default="BTCUSDT")
    interval: str = Field(default="1m")
    parameters: Optional[Dict[str, Any]] = None
    initial_cash: float = Field(default=10000.0, ge=100.0)
    cost_model: Optional[Dict[str, Any]] = None
    cost_assumptions: Optional[Dict[str, Any]] = None
    stress_scenarios: bool = Field(default=True)
    execution_delay_bars: int = Field(default=0, ge=0, le=10)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=500, ge=30, le=2000)


class TradeResponseSchema(BaseModel):
    trade_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: str
    fill_price: float
    quantity: float
    gross_notional: float
    fee: float
    slippage_cost: float
    realized_gross_pnl: float
    realized_net_pnl: float


class EquitySnapshotSchema(BaseModel):
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


class BacktestRunResponse(BaseModel):
    id: str
    strategy_id: str
    strategy_version: str
    config_id: str
    symbol: str
    interval: str
    time_range_start: datetime
    time_range_end: datetime
    candle_count: int
    dataset_fingerprint: str
    parameters: Dict[str, Any]
    cost_assumptions: Dict[str, Any]
    status: str
    metrics: Dict[str, Any]
    total_trades: int
    net_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: Optional[float] = None
    win_rate_pct: float
    created_at: datetime
    completed_at: Optional[datetime] = None
    equity_curve: Optional[List[EquitySnapshotSchema]] = None
    trades: Optional[List[TradeResponseSchema]] = None
    regime_performance: Optional[Dict[str, Any]] = None
    stress_test_results: Optional[Dict[str, Any]] = None

    @field_validator("profit_factor", mode="before")
    @classmethod
    def sanitize_profit_factor(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            val = float(v)
            return round(val, 4) if math.isfinite(val) else None
        except (ValueError, TypeError):
            return None

    @field_validator("sharpe_ratio", "net_return_pct", "max_drawdown_pct", "win_rate_pct", mode="before")
    @classmethod
    def sanitize_floats(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            val = float(v)
            return round(val, 4) if math.isfinite(val) else 0.0
        except (ValueError, TypeError):
            return 0.0

    @field_validator("metrics", mode="before")
    @classmethod
    def sanitize_metrics(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            clean = {}
            for k, val in v.items():
                if isinstance(val, float) and not math.isfinite(val):
                    clean[k] = None
                else:
                    clean[k] = val
            return clean
        return v or {}


class BacktestListResponse(BaseModel):
    count: int
    backtests: List[BacktestRunResponse]


class PerformanceAnalyticsResponse(BaseModel):
    strategy_id: Optional[str] = None
    total_backtests: int
    avg_net_return_pct: float
    avg_sharpe_ratio: float
    avg_max_drawdown_pct: float
    best_net_return_pct: float
    worst_net_return_pct: float
    runs: List[Dict[str, Any]]
