from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple
from app.market.constants import (
    INTERVAL_TO_SECONDS,
    SUPPORTED_INTERVALS,
)
from app.market.exceptions import CandleValidationException


def validate_candle(candle: Dict[str, Any]) -> None:
    """
    Validates timestamps, prices, volumes, and integrity constraints of an OHLCV candle.
    Raises CandleValidationException on any violation.
    """
    interval = candle.get("interval")
    if interval not in SUPPORTED_INTERVALS:
        raise CandleValidationException(
            f"Unsupported interval '{interval}'",
            details={"interval": interval, "allowed": SUPPORTED_INTERVALS},
        )

    # Validate timestamps
    open_time: datetime = candle.get("open_time")
    close_time: datetime = candle.get("close_time")

    if not isinstance(open_time, datetime) or not isinstance(close_time, datetime):
        raise CandleValidationException(
            "Timestamps must be valid datetime objects",
            details={"open_time": str(open_time), "close_time": str(close_time)},
        )

    if close_time <= open_time:
        raise CandleValidationException(
            "close_time must be strictly greater than open_time",
            details={"open_time": open_time.isoformat(), "close_time": close_time.isoformat()},
        )

    # Validate prices
    try:
        o = float(candle["open"])
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])
        v = float(candle["volume"])
    except (KeyError, ValueError, TypeError) as exc:
        raise CandleValidationException(f"Invalid numeric price or volume field: {exc}")

    if o < 0 or h < 0 or l < 0 or c < 0 or v < 0:
        raise CandleValidationException(
            "Prices and volume cannot be negative",
            details={"open": o, "high": h, "low": l, "close": c, "volume": v},
        )

    if h < l:
        raise CandleValidationException(
            "High price cannot be less than low price",
            details={"high": h, "low": l},
        )

    if h < max(o, c) or l > min(o, c):
        raise CandleValidationException(
            "High must be >= max(open, close) and Low must be <= min(open, close)",
            details={"open": o, "high": h, "low": l, "close": c},
        )


def validate_candle_sequence(candles: List[Dict[str, Any]]) -> None:
    """
    Validates candle ordering and absence of duplicate timestamps within a batch.
    """
    if len(candles) <= 1:
        return

    for i in range(len(candles) - 1):
        curr_time: datetime = candles[i]["open_time"]
        next_time: datetime = candles[i + 1]["open_time"]

        if next_time < curr_time:
            raise CandleValidationException(
                "Candles in batch are out of order",
                details={
                    "index": i,
                    "current_open_time": curr_time.isoformat(),
                    "next_open_time": next_time.isoformat(),
                },
            )
        elif next_time == curr_time:
            raise CandleValidationException(
                "Duplicate candle timestamp detected in batch",
                details={"open_time": curr_time.isoformat()},
            )


def detect_missing_intervals(
    candles: List[Any],
    interval: str,
) -> List[Tuple[datetime, datetime]]:
    """
    Detects gaps in a sequence of candles based on expected interval delta.
    Returns a list of missing ranges: [(gap_start_open_time, gap_end_open_time), ...]
    Zero synthetic candles are created.
    """
    if len(candles) < 2:
        return []

    interval_sec = INTERVAL_TO_SECONDS.get(interval, 60)
    expected_step = timedelta(seconds=interval_sec)
    gaps: List[Tuple[datetime, datetime]] = []

    for i in range(len(candles) - 1):
        curr_t = candles[i].open_time if hasattr(candles[i], "open_time") else candles[i]["open_time"]
        next_t = candles[i + 1].open_time if hasattr(candles[i + 1], "open_time") else candles[i + 1]["open_time"]

        if curr_t.tzinfo is None:
            curr_t = curr_t.replace(tzinfo=timezone.utc)
        if next_t.tzinfo is None:
            next_t = next_t.replace(tzinfo=timezone.utc)

        if next_t - curr_t > expected_step:
            gap_start = curr_t + expected_step
            gap_end = next_t - expected_step
            gaps.append((gap_start, gap_end))

    return gaps


def is_data_stale(
    last_update_utc: datetime | None,
    interval: str,
    max_stale_multiplier: float = 3.0,
) -> bool:
    """
    Checks if market feed has become stale based on time elapsed since the last observation.
    """
    if last_update_utc is None:
        return True

    now = datetime.now(timezone.utc)
    interval_sec = INTERVAL_TO_SECONDS.get(interval, 60)
    threshold = timedelta(seconds=interval_sec * max_stale_multiplier)

    # Ensure tz-awareness
    if last_update_utc.tzinfo is None:
        last_update_utc = last_update_utc.replace(tzinfo=timezone.utc)

    return (now - last_update_utc) > threshold
