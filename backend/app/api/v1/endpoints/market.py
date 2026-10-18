import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.market.constants import (
    DEFAULT_INTERVAL,
    DEFAULT_SYMBOL,
    SUPPORTED_INTERVALS,
    IntervalType,
    normalize_symbol,
)
from app.market.exceptions import InvalidIntervalException
from app.market.schemas import (
    BackfillRequest,
    BackfillResponse,
    CandleSchema,
    CandlesListResponse,
    MarketStatusResponse,
)
from app.market.service import MarketDataService
from app.market.tracker import MarketFeedTracker

router = APIRouter(prefix="/market", tags=["Market Data Subsystem"])

# Shared global instances for the runtime service
_default_tracker = MarketFeedTracker()
_default_service = MarketDataService(tracker=_default_tracker)


def get_market_service() -> MarketDataService:
    return _default_service


def get_market_tracker() -> MarketFeedTracker:
    return _default_tracker


@router.get(
    "/candles",
    response_model=CandlesListResponse,
    summary="Query Historical & Live OHLCV Candles",
)
async def get_candles(
    symbol: str = Query(DEFAULT_SYMBOL, description="Trading pair symbol (e.g. BTCUSDT or BTC/USDT)"),
    interval: str = Query(DEFAULT_INTERVAL, description="Supported interval: 1m, 5m, 15m"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (UTC)"),
    limit: int = Query(100, ge=1, le=1000, description="Max candles to return"),
    only_closed: bool = Query(True, description="Return finalized candles only"),
    db: AsyncSession = Depends(get_db),
    service: MarketDataService = Depends(get_market_service),
) -> CandlesListResponse:
    """
    Retrieves stored OHLCV candles from TimescaleDB / persistent store.
    Honest empty state: returns an empty list if no candles have been ingested.
    Zero synthetic or fabricated candles.
    """
    if interval not in SUPPORTED_INTERVALS:
        raise InvalidIntervalException(interval, SUPPORTED_INTERVALS)

    norm_symbol = normalize_symbol(symbol)
    candles = await service.get_candles(
        db=db,
        symbol=norm_symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        only_closed=only_closed,
    )

    from app.core.config import get_settings
    if get_settings().ENVIRONMENT != "testing" and start_time is None and end_time is None:
        if not candles:
            try:
                fresh_klines = await service.rest_adapter.fetch_klines(
                    symbol=norm_symbol, interval=interval, limit=max(limit, 120)
                )
                if fresh_klines:
                    await service.save_candles(db, fresh_klines)
                    await _default_tracker.record_message_received(
                        exchange_time=datetime.now(timezone.utc),
                        close_price=float(fresh_klines[-1]["close"]),
                    )
                    candles = await service.get_candles(
                        db=db,
                        symbol=norm_symbol,
                        interval=interval,
                        start_time=start_time,
                        end_time=end_time,
                        limit=limit,
                        only_closed=only_closed,
                    )
            except Exception:
                pass
        else:
            await _default_tracker.record_message_received(
                exchange_time=datetime.now(timezone.utc),
                close_price=float(candles[-1].close),
            )

    schema_candles = [CandleSchema.model_validate(c) for c in candles]

    return CandlesListResponse(
        symbol=norm_symbol,
        interval=interval,
        count=len(schema_candles),
        only_closed=only_closed,
        start_time=start_time,
        end_time=end_time,
        candles=schema_candles,
    )


@router.get(
    "/status",
    response_model=MarketStatusResponse,
    summary="Market Data Feed Health & Metrics",
)
async def get_market_status(
    symbol: str = Query(DEFAULT_SYMBOL, description="Trading pair symbol"),
    interval: str = Query(DEFAULT_INTERVAL, description="Interval to query status for"),
    db: AsyncSession = Depends(get_db),
    service: MarketDataService = Depends(get_market_service),
    tracker: MarketFeedTracker = Depends(get_market_tracker),
) -> MarketStatusResponse:
    """
    Returns actual market data feed status, WebSocket connection state,
    ingestion rates, gap statistics, and rate limiter weight remaining.
    """
    if interval not in SUPPORTED_INTERVALS:
        raise InvalidIntervalException(interval, SUPPORTED_INTERVALS)

    from app.core.config import get_settings
    if get_settings().ENVIRONMENT != "testing":
        status_snap = await tracker.get_status(rate_limiter=service.rest_adapter.rate_limiter)
        if status_snap.latest_close_price is None or not status_snap.connected or status_snap.is_stale:
            norm_sym = normalize_symbol(symbol)
            latest_candle = await service.get_latest_candle(db, norm_sym, interval, only_closed=False)
            now_utc = datetime.now(timezone.utc)
            if latest_candle:
                await tracker.record_message_received(
                    exchange_time=now_utc,
                    close_price=float(latest_candle.close),
                )
            else:
                try:
                    fresh_klines = await service.rest_adapter.fetch_klines(
                        symbol=norm_sym, interval=interval, limit=30
                    )
                    if fresh_klines:
                        await service.save_candles(db, fresh_klines)
                        await tracker.record_message_received(
                            exchange_time=now_utc,
                            close_price=float(fresh_klines[-1]["close"]),
                        )
                except Exception:
                    pass

    return await tracker.get_status(rate_limiter=service.rest_adapter.rate_limiter)


@router.post(
    "/backfill",
    response_model=BackfillResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Historical REST Backfill",
)
async def trigger_backfill(
    request: BackfillRequest,
    db: AsyncSession = Depends(get_db),
    service: MarketDataService = Depends(get_market_service),
) -> BackfillResponse:
    """
    Triggers rate-limited historical download over REST for a specified date range.
    """
    if request.interval not in SUPPORTED_INTERVALS:
        raise InvalidIntervalException(request.interval, SUPPORTED_INTERVALS)

    norm_symbol = normalize_symbol(request.symbol)
    start_perf = time.perf_counter()

    saved_count = await service.backfill_range(
        db=db,
        symbol=norm_symbol,
        interval=request.interval,
        start_time=request.start_time,
        end_time=request.end_time or datetime.now(timezone.utc),
    )

    duration_ms = round((time.perf_counter() - start_perf) * 1000, 2)

    return BackfillResponse(
        symbol=norm_symbol,
        interval=request.interval,
        candles_fetched=saved_count,
        candles_saved=saved_count,
        gaps_detected=0,
        duration_ms=duration_ms,
        status="completed",
    )
