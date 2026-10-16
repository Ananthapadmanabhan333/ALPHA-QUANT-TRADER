from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.service import MarketDataService


@pytest.mark.asyncio
async def test_list_strategies_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/strategies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    strategy_ids = [s["strategy_id"] for s in data]
    assert "trend_following" in strategy_ids
    assert "mean_reversion" in strategy_ids
    assert "momentum" in strategy_ids


@pytest.mark.asyncio
async def test_run_strategy_not_found_candles(client: AsyncClient):
    response = await client.post(
        "/api/v1/strategies/run",
        json={"strategy_id": "trend_following", "symbol": "BTCUSDT", "interval": "1m"},
    )
    res = response.json()
    msg = res.get("error", {}).get("message") or res.get("detail", "")
    assert "No finalized candles found" in msg


@pytest.mark.asyncio
async def test_run_strategy_success(client: AsyncClient, test_session: AsyncSession):
    # Ingest 120 deterministic synthetic candles
    market_service = MarketDataService()
    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(120):
        candles.append({
            "symbol": "BTCUSDT",
            "interval": "1m",
            "open_time": t0 + timedelta(minutes=i),
            "close_time": t0 + timedelta(minutes=i, seconds=59),
            "open": 50000.0 + i,
            "high": 50010.0 + i,
            "low": 49990.0 + i,
            "close": 50005.0 + i,
            "volume": 15.0,
            "quote_volume": 750000.0,
            "trades_count": 50,
            "is_closed": True,
            "source": "quant_test",
            "ingested_at": datetime.now(timezone.utc),
        })
    await market_service.save_candles(test_session, candles)

    # Run strategy
    response = await client.post(
        "/api/v1/strategies/run",
        json={
            "strategy_id": "trend_following",
            "symbol": "BTCUSDT",
            "interval": "1m",
            "limit": 120,
        },
    )
    assert response.status_code == 201
    exp = response.json()
    assert exp["strategy_id"] == "trend_following"
    assert exp["candle_count"] == 120
    assert len(exp["dataset_fingerprint"]) == 64
    assert exp["total_signals"] == 120
    assert len(exp["signals"]) == 120

    experiment_id = exp["id"]

    # List experiments
    list_resp = await client.get("/api/v1/strategies/experiments")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["count"] >= 1
    assert any(e["id"] == experiment_id for e in list_data["experiments"])

    # Get specific experiment
    get_resp = await client.get(f"/api/v1/strategies/experiments/{experiment_id}")
    assert get_resp.status_code == 200
    exp_details = get_resp.json()
    assert exp_details["id"] == experiment_id
    assert len(exp_details["signals"]) == 120
