from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import get_settings
from app.core.logging import get_logger
from app.market.constants import (
    BINANCE_REST_BASE_URL,
    DEFAULT_KLINES_LIMIT,
    INTERVAL_TO_MS,
    MAX_KLINES_LIMIT,
    SUPPORTED_INTERVALS,
    normalize_symbol,
)
from app.market.exceptions import (
    ExchangeConnectionException,
    InvalidIntervalException,
    RateLimitExceededException,
)
from app.market.rate_limiter import AsyncRateLimiter
from app.market.validator import validate_candle, validate_candle_sequence

logger = get_logger("market.rest")


class BinanceRestAdapter:
    """
    Production-grade adapter for Binance Spot Public REST API.
    Does not require exchange API keys.
    Extracts, normalizes, validates, and paginates OHLCV historical klines.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        rate_limiter: Optional[AsyncRateLimiter] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.BINANCE_REST_BASE_URL).rstrip("/")
        self.rate_limiter = rate_limiter or AsyncRateLimiter(settings.MARKET_DATA_RATE_LIMIT_PER_MINUTE)
        self._external_client = client
        self._internal_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._internal_client is None or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(timeout=15.0)
        return self._internal_client

    async def close(self) -> None:
        if self._internal_client and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    def _parse_raw_kline(
        self,
        item: list,
        symbol: str,
        interval: str,
        ingested_at: datetime,
    ) -> Dict[str, Any]:
        """Convert Binance raw kline array to validated normalized dictionary."""
        open_time_ms = int(item[0])
        close_time_ms = int(item[6])

        open_time = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)
        close_time = datetime.fromtimestamp(close_time_ms / 1000.0, tz=timezone.utc)

        # A candle is closed if its close time is in the past
        is_closed = close_time <= ingested_at

        candle_data = {
            "symbol": symbol,
            "interval": interval,
            "open_time": open_time,
            "close_time": close_time,
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
            "quote_volume": float(item[7]),
            "trades_count": int(item[8]),
            "taker_buy_base_volume": float(item[9]),
            "taker_buy_quote_volume": float(item[10]),
            "is_closed": is_closed,
            "source": "binance_spot",
            "exchange_event_time": close_time,
            "ingested_at": ingested_at,
        }
        validate_candle(candle_data)
        return candle_data

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime | int] = None,
        end_time: Optional[datetime | int] = None,
        limit: int = DEFAULT_KLINES_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Fetch a single batch of klines from GET /api/v3/klines.
        Rate-limited, validated, and normalized.
        """
        norm_symbol = normalize_symbol(symbol)
        if interval not in SUPPORTED_INTERVALS:
            raise InvalidIntervalException(interval, SUPPORTED_INTERVALS)

        limit = min(max(1, limit), MAX_KLINES_LIMIT)
        params: Dict[str, Any] = {
            "symbol": norm_symbol,
            "interval": interval,
            "limit": limit,
        }

        if start_time is not None:
            if isinstance(start_time, datetime):
                params["startTime"] = int(start_time.timestamp() * 1000)
            else:
                params["startTime"] = int(start_time)

        if end_time is not None:
            if isinstance(end_time, datetime):
                params["endTime"] = int(end_time.timestamp() * 1000)
            else:
                params["endTime"] = int(end_time)

        # Enforce rate limiter before issuing request
        await self.rate_limiter.acquire(weight=2)

        client = await self._get_client()
        url = f"{self.base_url}/api/v3/klines"

        try:
            response = await client.get(url, params=params)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("binance_rest_connection_error", error=str(exc), url=url)
            raise ExchangeConnectionException(f"Network error communicating with Binance: {exc}")

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 60))
            logger.error("binance_rate_limit_exceeded", retry_after=retry_after)
            raise RateLimitExceededException(retry_after_seconds=retry_after)

        if not response.is_success:
            logger.error(
                "binance_rest_error_status",
                status_code=response.status_code,
                text=response.text,
            )
            raise ExchangeConnectionException(
                f"Binance returned status {response.status_code}: {response.text}"
            )

        raw_data = response.json()
        if not isinstance(raw_data, list):
            raise ExchangeConnectionException("Unexpected response payload format from Binance")

        ingested_at = datetime.now(timezone.utc)
        parsed_candles = [
            self._parse_raw_kline(item, norm_symbol, interval, ingested_at)
            for item in raw_data
        ]

        validate_candle_sequence(parsed_candles)
        return parsed_candles

    async def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        max_candles: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginates backwards or forwards over a continuous date range.
        Respects rate limits across multiple HTTP calls.
        """
        norm_symbol = normalize_symbol(symbol)
        interval_ms = INTERVAL_TO_MS[interval]
        current_start_ms = int(start_time.timestamp() * 1000)
        end_ms = int((end_time or datetime.now(timezone.utc)).timestamp() * 1000)

        all_candles: List[Dict[str, Any]] = []

        while current_start_ms < end_ms:
            if max_candles and len(all_candles) >= max_candles:
                break

            batch_limit = MAX_KLINES_LIMIT
            if max_candles:
                batch_limit = min(batch_limit, max_candles - len(all_candles))

            batch = await self.fetch_klines(
                symbol=norm_symbol,
                interval=interval,
                start_time=current_start_ms,
                end_time=end_ms,
                limit=batch_limit,
            )

            if not batch:
                break

            all_candles.extend(batch)

            # Advance cursor past the last fetched candle
            last_open_ms = int(batch[-1]["open_time"].timestamp() * 1000)
            next_start_ms = last_open_ms + interval_ms

            if next_start_ms <= current_start_ms:
                # Avoid infinite loops if exchange returned duplicate timestamp
                break
            current_start_ms = next_start_ms

            if len(batch) < batch_limit:
                # Reached end of available data on exchange
                break

        return all_candles

    _global_mock_status: Optional[Dict[str, Any]] = None

    async def ping(self) -> Dict[str, Any]:
        """
        Verify connectivity and latency against Binance Spot public REST API.
        Used for operational readiness health checks.
        """
        if BinanceRestAdapter._global_mock_status is not None:
            return BinanceRestAdapter._global_mock_status

        settings = get_settings()
        if settings.ENVIRONMENT == "testing":
            mock_status = getattr(self, "_test_mock_status", None)
            if mock_status is not None:
                return mock_status
            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": 1.5,
                "source": "test_mock",
            }

        start_time = time.perf_counter()
        try:
            client = await self._get_client()
            res = await client.get(f"{self.base_url}/api/v3/ping", timeout=4.0)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if res.status_code == 200:
                return {
                    "status": "healthy",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "base_url": self.base_url,
                }
            return {
                "status": "unhealthy",
                "connected": False,
                "status_code": res.status_code,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(exc),
                "latency_ms": latency_ms,
            }
