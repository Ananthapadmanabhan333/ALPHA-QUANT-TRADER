from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.market.models import MarketCandle
from app.market.service import MarketDataService


def make_candle_dict(
    open_time: datetime,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    price: float = 65000.0,
    is_closed: bool = True,
) -> dict:
    return {
        "symbol": symbol,
        "interval": interval,
        "open_time": open_time,
        "close_time": open_time + timedelta(minutes=1),
        "open": price,
        "high": price + 50.0,
        "low": price - 50.0,
        "close": price + 10.0,
        "volume": 5.0,
        "quote_volume": 325000.0,
        "trades_count": 120,
        "is_closed": is_closed,
        "source": "unit_test",
        "ingested_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_idempotent_candle_upsert(test_session: AsyncSession):
    service = MarketDataService()
    t0 = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)

    # First insert: open candle
    open_c = make_candle_dict(t0, price=65000.0, is_closed=False)
    await service.save_candles(test_session, [open_c])

    stmt = select(MarketCandle).where(
        MarketCandle.symbol == "BTCUSDT",
        MarketCandle.interval == "1m",
        MarketCandle.open_time == t0,
    )
    res = await test_session.execute(stmt)
    c1 = res.scalar_one()
    assert c1.close == 65010.0
    assert c1.is_closed is False

    # Second insert with SAME primary key (symbol, interval, open_time): finalized candle
    closed_c = make_candle_dict(t0, price=65000.0, is_closed=True)
    closed_c["close"] = 65080.0
    await service.save_candles(test_session, [closed_c])

    # Must still have exactly 1 record, updated in place
    all_res = await test_session.execute(stmt)
    rows = list(all_res.scalars().all())
    assert len(rows) == 1
    assert rows[0].close == 65080.0
    assert rows[0].is_closed is True


@pytest.mark.asyncio
async def test_detect_gaps_in_database(test_session: AsyncSession):
    service = MarketDataService()
    t0 = datetime(2026, 10, 11, 9, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    # Skip minute 2 and 3
    t4 = t0 + timedelta(minutes=4)

    c0 = make_candle_dict(t0)
    c1 = make_candle_dict(t1)
    c4 = make_candle_dict(t4)

    await service.save_candles(test_session, [c0, c1, c4])

    gaps = await service.detect_gaps_in_db(
        test_session,
        symbol="BTCUSDT",
        interval="1m",
        start_time=t0,
        end_time=t4,
    )

    assert len(gaps) == 1
    # Missing interval between 9:02 and 9:03
    assert gaps[0][0] == t0 + timedelta(minutes=2)
    assert gaps[0][1] == t4 - timedelta(minutes=1)


@pytest.mark.asyncio
async def test_get_candles_filtering(test_session: AsyncSession):
    service = MarketDataService()
    t0 = datetime(2026, 10, 11, 7, 0, 0, tzinfo=timezone.utc)

    c_closed = make_candle_dict(t0, is_closed=True)
    c_open = make_candle_dict(t0 + timedelta(minutes=1), is_closed=False)

    await service.save_candles(test_session, [c_closed, c_open])

    # Filter only_closed = True
    closed_candles = await service.get_candles(test_session, symbol="BTCUSDT", interval="1m", only_closed=True)
    assert len(closed_candles) == 1
    assert closed_candles[0].is_closed is True

    # Filter only_closed = False
    all_candles = await service.get_candles(test_session, symbol="BTCUSDT", interval="1m", only_closed=False)
    assert len(all_candles) == 2
