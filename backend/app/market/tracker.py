import asyncio
from datetime import datetime, timezone
from typing import Optional
from app.market.constants import DEFAULT_INTERVAL, DEFAULT_SYMBOL
from app.market.rate_limiter import AsyncRateLimiter
from app.market.schemas import MarketStatusResponse
from app.market.validator import is_data_stale


class MarketFeedTracker:
    """
    Thread-safe / asyncio-safe in-memory health metrics and state tracker
    for the market data ingestion feeds.
    """
    def __init__(self, symbol: str = DEFAULT_SYMBOL, interval: str = DEFAULT_INTERVAL):
        self.symbol = symbol
        self.interval = interval
        self.feed_state: str = "DISCONNECTED"
        self.connected: bool = False
        self.is_streaming: bool = False
        self.last_exchange_time: Optional[datetime] = None
        self.last_ingested_at: Optional[datetime] = None
        self.latest_close_price: Optional[float] = None
        self.messages_received: int = 0
        self.candles_saved: int = 0
        self.gap_count: int = 0
        self.error_count: int = 0
        self.reconnect_count: int = 0
        self._lock = asyncio.Lock()

    async def record_connected(self) -> None:
        async with self._lock:
            self.connected = True
            self.feed_state = "STREAMING"
            self.is_streaming = True

    async def record_disconnected(self) -> None:
        async with self._lock:
            self.connected = False
            self.is_streaming = False
            self.feed_state = "DISCONNECTED"

    async def record_reconnect_attempt(self) -> None:
        async with self._lock:
            self.reconnect_count += 1
            self.feed_state = "CONNECTING"

    async def record_message_received(
        self,
        exchange_time: datetime,
        close_price: float,
    ) -> None:
        async with self._lock:
            self.messages_received += 1
            self.last_exchange_time = exchange_time
            self.last_ingested_at = datetime.now(timezone.utc)
            self.latest_close_price = close_price
            self.feed_state = "STREAMING"

    async def record_candles_saved(self, count: int) -> None:
        async with self._lock:
            self.candles_saved += count

    async def record_gap_detected(self, gaps_count: int = 1) -> None:
        async with self._lock:
            self.gap_count += gaps_count

    async def record_error(self) -> None:
        async with self._lock:
            self.error_count += 1
            if not self.connected:
                self.feed_state = "ERROR"

    async def record_backfill_state(self, is_active: bool) -> None:
        async with self._lock:
            if is_active:
                self.feed_state = "BACKFILLING"
            else:
                self.feed_state = "STREAMING" if self.connected else "DISCONNECTED"

    async def get_status(self, rate_limiter: Optional[AsyncRateLimiter] = None) -> MarketStatusResponse:
        async with self._lock:
            stale = is_data_stale(self.last_exchange_time, self.interval) if self.connected else False
            effective_state = "STALE" if (self.connected and stale) else self.feed_state

            remaining_weight = rate_limiter.remaining_weight() if rate_limiter else 1200

            return MarketStatusResponse(
                symbol=self.symbol,
                interval=self.interval,
                feed_state=effective_state,
                connected=self.connected,
                is_streaming=self.is_streaming,
                last_exchange_time=self.last_exchange_time,
                last_ingested_at=self.last_ingested_at,
                latest_close_price=self.latest_close_price,
                messages_received=self.messages_received,
                candles_saved=self.candles_saved,
                gap_count=self.gap_count,
                error_count=self.error_count,
                reconnect_count=self.reconnect_count,
                is_stale=stale,
                rate_limit_remaining=remaining_weight,
                timestamp=datetime.now(timezone.utc),
            )
