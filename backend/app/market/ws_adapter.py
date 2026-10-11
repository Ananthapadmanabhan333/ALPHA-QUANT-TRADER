import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Callable, Coroutine, Dict, Optional
import websockets
from app.core.config import get_settings
from app.core.logging import get_logger
from app.market.backoff import compute_exponential_backoff_jitter
from app.market.constants import BINANCE_WS_BASE_URL, normalize_symbol
from app.market.tracker import MarketFeedTracker
from app.market.validator import validate_candle

logger = get_logger("market.ws")

CandleCallback = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class BinanceWsAdapter:
    """
    Public WebSocket adapter for Binance Spot kline streams.
    Handles continuous streaming, exponential backoff with full jitter,
    message validation, metrics tracking, and graceful shutdown.
    """
    def __init__(
        self,
        symbol: str,
        interval: str,
        on_candle: Optional[CandleCallback] = None,
        tracker: Optional[MarketFeedTracker] = None,
        base_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.symbol = normalize_symbol(symbol)
        self.interval = interval
        self.on_candle = on_candle
        self.tracker = tracker or MarketFeedTracker(self.symbol, self.interval)
        self.base_url = (base_url or settings.BINANCE_WS_BASE_URL).rstrip("/")
        self.initial_backoff = settings.MARKET_DATA_WS_INITIAL_BACKOFF_SECONDS
        self.max_backoff = settings.MARKET_DATA_WS_MAX_BACKOFF_SECONDS

        self.shutdown_event = asyncio.Event()
        self._running_task: Optional[asyncio.Task] = None

    @property
    def stream_url(self) -> str:
        stream_name = f"{self.symbol.lower()}@kline_{self.interval}"
        return f"{self.base_url}/{stream_name}"

    def parse_ws_message(self, raw_message: str | bytes) -> Dict[str, Any]:
        """
        Parses and validates Binance kline WebSocket payload.
        Distinguishes open candles (x=false) from finalized candles (x=true).
        """
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in WebSocket message: {exc}")

        if "k" not in payload:
            raise ValueError("Malformed Binance kline payload: missing 'k' object")

        k = payload["k"]
        exchange_event_time_ms = payload.get("E")
        exchange_event_time = (
            datetime.fromtimestamp(exchange_event_time_ms / 1000.0, tz=timezone.utc)
            if exchange_event_time_ms
            else None
        )

        open_time = datetime.fromtimestamp(int(k["t"]) / 1000.0, tz=timezone.utc)
        close_time = datetime.fromtimestamp(int(k["T"]) / 1000.0, tz=timezone.utc)
        ingested_at = datetime.now(timezone.utc)

        candle_data: Dict[str, Any] = {
            "symbol": payload.get("s", self.symbol),
            "interval": k["i"],
            "open_time": open_time,
            "close_time": close_time,
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
            "quote_volume": float(k["q"]),
            "trades_count": int(k["n"]),
            "taker_buy_base_volume": float(k["V"]),
            "taker_buy_quote_volume": float(k["Q"]),
            "is_closed": bool(k["x"]),  # Key: True if finalized, False if open/forming
            "source": "binance_spot_ws",
            "exchange_event_time": exchange_event_time,
            "ingested_at": ingested_at,
        }

        validate_candle(candle_data)
        return candle_data

    async def _run_stream(self) -> None:
        reconnect_attempts = 0

        while not self.shutdown_event.is_set():
            try:
                await self.tracker.record_reconnect_attempt()
                logger.info(
                    "connecting_binance_websocket",
                    url=self.stream_url,
                    attempt=reconnect_attempts,
                )

                async with websockets.connect(
                    self.stream_url,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=5,
                ) as ws:
                    await self.tracker.record_connected()
                    reconnect_attempts = 0
                    logger.info("binance_websocket_connected", stream=self.stream_url)

                    while not self.shutdown_event.is_set():
                        try:
                            # 1 second timeout enables periodic shutdown check
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue

                        try:
                            candle = self.parse_ws_message(raw_msg)
                            await self.tracker.record_message_received(
                                exchange_time=candle["exchange_event_time"] or candle["open_time"],
                                close_price=candle["close"],
                            )

                            if self.on_candle:
                                await self.on_candle(candle)

                        except Exception as parse_err:
                            await self.tracker.record_error()
                            logger.warning(
                                "malformed_ws_candle_event",
                                error=str(parse_err),
                            )

            except asyncio.CancelledError:
                logger.info("binance_ws_task_cancelled")
                break
            except Exception as conn_err:
                reconnect_attempts += 1
                await self.tracker.record_disconnected()
                await self.tracker.record_error()

                if self.shutdown_event.is_set():
                    break

                delay = compute_exponential_backoff_jitter(
                    reconnect_attempts,
                    self.initial_backoff,
                    self.max_backoff,
                )
                logger.warning(
                    "binance_ws_disconnected_reconnecting",
                    error=str(conn_err),
                    reconnect_attempts=reconnect_attempts,
                    delay_seconds=round(delay, 2),
                )
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    break

        await self.tracker.record_disconnected()
        logger.info("binance_ws_stream_stopped")

    def start(self) -> asyncio.Task:
        """Starts the WebSocket ingestion stream in the background."""
        self.shutdown_event.clear()
        self._running_task = asyncio.create_task(self._run_stream())
        return self._running_task

    async def stop(self) -> None:
        """Gracefully halts the WebSocket ingestion stream."""
        logger.info("stopping_binance_websocket")
        self.shutdown_event.set()
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            try:
                await self._running_task
            except asyncio.CancelledError:
                pass
        self._running_task = None
        await self.tracker.record_disconnected()
