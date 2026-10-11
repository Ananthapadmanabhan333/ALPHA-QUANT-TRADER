from datetime import datetime, timezone, timedelta
import pytest
from app.market.exceptions import CandleValidationException
from app.market.validator import (
    validate_candle,
    validate_candle_sequence,
    detect_missing_intervals,
    is_data_stale,
)


def create_sample_candle(
    open_time: datetime,
    close_time: datetime,
    open_p: float = 60000.0,
    high_p: float = 60500.0,
    low_p: float = 59800.0,
    close_p: float = 60200.0,
    volume: float = 10.5,
    interval: str = "1m",
    symbol: str = "BTCUSDT",
    is_closed: bool = True,
) -> dict:
    return {
        "symbol": symbol,
        "interval": interval,
        "open_time": open_time,
        "close_time": close_time,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": volume,
        "is_closed": is_closed,
        "ingested_at": datetime.now(timezone.utc),
    }


def test_valid_candle():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candle = create_sample_candle(t0, t1)
    # Should not raise
    validate_candle(candle)


def test_invalid_interval():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candle = create_sample_candle(t0, t1, interval="2h")
    with pytest.raises(CandleValidationException, match="Unsupported interval"):
        validate_candle(candle)


def test_invalid_price_relationships():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)

    # High < Low
    candle = create_sample_candle(t0, t1, high_p=59000.0, low_p=60000.0)
    with pytest.raises(CandleValidationException, match="High price cannot be less than low"):
        validate_candle(candle)

    # High < Close
    candle = create_sample_candle(t0, t1, high_p=60000.0, close_p=60100.0)
    with pytest.raises(CandleValidationException, match="High must be >= max"):
        validate_candle(candle)

    # Low > Open
    candle = create_sample_candle(t0, t1, low_p=60100.0, open_p=60000.0)
    with pytest.raises(CandleValidationException, match="Low must be <= min"):
        validate_candle(candle)


def test_negative_values():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    candle = create_sample_candle(t0, t1, volume=-1.0)
    with pytest.raises(CandleValidationException, match="cannot be negative"):
        validate_candle(candle)


def test_invalid_timestamps():
    t0 = datetime(2026, 10, 11, 10, 1, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    candle = create_sample_candle(t0, t1)
    with pytest.raises(CandleValidationException, match="close_time must be strictly greater"):
        validate_candle(candle)


def test_sequence_ordering_and_duplicates():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    t2 = t0 + timedelta(minutes=2)

    c0 = create_sample_candle(t0, t0 + timedelta(minutes=1))
    c1 = create_sample_candle(t1, t1 + timedelta(minutes=1))
    c2 = create_sample_candle(t2, t2 + timedelta(minutes=1))

    # Valid ordered sequence
    validate_candle_sequence([c0, c1, c2])

    # Out of order
    with pytest.raises(CandleValidationException, match="out of order"):
        validate_candle_sequence([c1, c0, c2])

    # Duplicate timestamp
    with pytest.raises(CandleValidationException, match="Duplicate candle timestamp"):
        validate_candle_sequence([c0, c0, c2])


def test_detect_missing_intervals():
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    c0 = create_sample_candle(t0, t0 + timedelta(minutes=1))
    # Skip minute 10:01 and 10:02
    t3 = t0 + timedelta(minutes=3)
    c3 = create_sample_candle(t3, t3 + timedelta(minutes=1))

    gaps = detect_missing_intervals([c0, c3], interval="1m")
    assert len(gaps) == 1
    # Expected gap from 10:01 to 10:02
    assert gaps[0][0] == t0 + timedelta(minutes=1)
    assert gaps[0][1] == t3 - timedelta(minutes=1)


def test_staleness_detector():
    now = datetime.now(timezone.utc)
    # Recent candle (30 seconds ago) -> not stale for 1m
    assert is_data_stale(now - timedelta(seconds=30), interval="1m") is False
    # Old candle (10 minutes ago) -> stale for 1m
    assert is_data_stale(now - timedelta(minutes=10), interval="1m") is True
    # None timestamp -> stale
    assert is_data_stale(None, interval="1m") is True
