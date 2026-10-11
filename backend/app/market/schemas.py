from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.market.constants import IntervalType, DEFAULT_SYMBOL, DEFAULT_INTERVAL


class CandleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str = Field(..., description="Trading pair symbol (e.g. BTCUSDT)")
    interval: str = Field(..., description="Candle interval (e.g. 1m, 5m, 15m)")
    open_time: datetime = Field(..., description="Exchange candle start timestamp in UTC")
    close_time: datetime = Field(..., description="Exchange candle close timestamp in UTC")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price during interval")
    low: float = Field(..., description="Lowest price during interval")
    close: float = Field(..., description="Closing / last observed price")
    volume: float = Field(..., description="Base asset volume traded")
    quote_volume: float = Field(default=0.0, description="Quote asset volume traded")
    trades_count: int = Field(default=0, description="Total number of trades")
    is_closed: bool = Field(default=True, description="True if candle is finalized; False if currently forming")
    source: str = Field(default="binance_spot", description="Originating exchange feed")
    exchange_event_time: Optional[datetime] = Field(default=None, description="Event emission timestamp in UTC")
    ingested_at: datetime = Field(..., description="System ingestion timestamp in UTC")


class CandlesListResponse(BaseModel):
    symbol: str
    interval: str
    count: int
    only_closed: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    candles: List[CandleSchema]


class MarketStatusResponse(BaseModel):
    symbol: str
    interval: str
    feed_state: str = Field(..., description="DISCONNECTED, CONNECTING, STREAMING, BACKFILLING, STALE, ERROR")
    connected: bool
    is_streaming: bool
    last_exchange_time: Optional[datetime] = None
    last_ingested_at: Optional[datetime] = None
    latest_close_price: Optional[float] = None
    messages_received: int = 0
    candles_saved: int = 0
    gap_count: int = 0
    error_count: int = 0
    reconnect_count: int = 0
    is_stale: bool = False
    rate_limit_remaining: int = 1200
    timestamp: datetime


class BackfillRequest(BaseModel):
    symbol: str = DEFAULT_SYMBOL
    interval: IntervalType = DEFAULT_INTERVAL
    start_time: datetime
    end_time: Optional[datetime] = None


class BackfillResponse(BaseModel):
    symbol: str
    interval: str
    candles_fetched: int
    candles_saved: int
    gaps_detected: int
    duration_ms: float
    status: str
