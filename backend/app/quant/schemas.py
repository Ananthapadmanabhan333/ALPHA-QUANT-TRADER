from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategyInfoSchema(BaseModel):
    strategy_id: str
    name: str
    version: str
    description: str
    candidate_parameters: Dict[str, Any]
    features_used: List[str]


class RunStrategyRequest(BaseModel):
    strategy_id: str
    symbol: str = Field(default="BTCUSDT")
    interval: str = Field(default="1m")
    parameters: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=300, ge=10, le=2000)


class SignalResponseSchema(BaseModel):
    strategy_id: str
    strategy_version: str
    decision_timestamp: datetime
    symbol: str
    side: str
    signal_score: float
    reference_price: float
    reason: str
    relevant_features: Dict[str, Optional[float]]
    config_id: str


class ExperimentResponseSchema(BaseModel):
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
    total_signals: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    created_at: datetime
    signals: Optional[List[SignalResponseSchema]] = None


class ExperimentListResponse(BaseModel):
    count: int
    experiments: List[ExperimentResponseSchema]


class LiveIndicatorsSchema(BaseModel):
    close: float
    sma_20: Optional[float] = None
    sma_100: Optional[float] = None
    ema_20: Optional[float] = None
    trend_spread_bps: Optional[float] = None
    zscore_60: Optional[float] = None
    atr_14: Optional[float] = None
    atr_bps: Optional[float] = None
    volatility_20: Optional[float] = None
    momentum_5: Optional[float] = None
    momentum_15: Optional[float] = None
    momentum_60: Optional[float] = None
    volume_ratio_20: Optional[float] = None


class LiveTradeSetupSchema(BaseModel):
    strategy_id: str
    strategy_name: str
    side: str
    signal_score: float
    reason: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_ratio: float
    recommended_qty: float
    recommended_notional_usd: float
    relevant_features: Dict[str, Optional[float]]


class LiveScannerResponseSchema(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    regime: str
    consensus_side: str
    consensus_score: float
    indicators: LiveIndicatorsSchema
    setups: List[LiveTradeSetupSchema]

