from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.market.service import MarketDataService


@pytest.mark.asyncio
async def test_get_candles_honest_empty_state(client: AsyncClient):
    """Verifies honest empty state: returns count=0 and empty list with zero mock data."""
    response = await client.get("/api/v1/market/candles?symbol=BTCUSDT&interval=1m")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["interval"] == "1m"
    assert data["count"] == 0
    assert data["candles"] == []


@pytest.mark.asyncio
async def test_get_candles_with_data(client: AsyncClient, test_session: AsyncSession):
    t0 = datetime(2026, 10, 11, 11, 0, 0, tzinfo=timezone.utc)
    service = MarketDataService()
    candle = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "open_time": t0,
        "close_time": t0 + timedelta(minutes=1),
        "open": 64000.0,
        "high": 64200.0,
        "low": 63900.0,
        "close": 64150.0,
        "volume": 8.5,
        "quote_volume": 545000.0,
        "trades_count": 210,
        "is_closed": True,
        "source": "api_test",
        "ingested_at": datetime.now(timezone.utc),
    }
    await service.save_candles(test_session, [candle])

    response = await client.get("/api/v1/market/candles?symbol=BTCUSDT&interval=1m")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["candles"]) == 1
    c = data["candles"][0]
    assert c["symbol"] == "BTCUSDT"
    assert c["close"] == 64150.0
    assert c["is_closed"] is True


@pytest.mark.asyncio
async def test_get_candles_invalid_interval(client: AsyncClient):
    response = await client.get("/api/v1/market/candles?symbol=BTCUSDT&interval=4h")
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_INTERVAL"


@pytest.mark.asyncio
async def test_get_market_status(client: AsyncClient):
    response = await client.get("/api/v1/market/status?symbol=BTCUSDT&interval=1m")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["interval"] == "1m"
    assert "feed_state" in data
    assert "connected" in data
    assert "rate_limit_remaining" in data
    assert "timestamp" in data
