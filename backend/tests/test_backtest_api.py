"""
Unit and integration tests for Backtesting REST API endpoints:
- POST /api/v1/backtests
- GET /api/v1/backtests
- GET /api/v1/backtests/{run_id}
- GET /api/v1/analytics/performance
"""

from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.service import MarketDataService


@pytest.mark.asyncio
async def test_backtest_api_unsupported_strategy(client: AsyncClient):
    response = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "non_existent_strategy",
            "symbol": "BTCUSDT",
            "interval": "1m",
        },
    )
    assert response.status_code == 400
    assert "Unsupported strategy" in response.text


@pytest.mark.asyncio
async def test_backtest_api_insufficient_data(client: AsyncClient):
    response = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "trend_following",
            "symbol": "BTCUSDT",
            "interval": "1m",
            "start_time": "2020-01-01T00:00:00Z",
            "end_time": "2020-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 400
    assert "No finalized candles found" in response.text or "requires at least" in response.text


@pytest.mark.asyncio
async def test_backtest_api_lifecycle_and_analytics(client: AsyncClient, test_session: AsyncSession):
    # 1. Seed 140 deterministic candles to fulfill warmup requirements
    market_service = MarketDataService()
    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    candles = []
    base_price = 50000.0

    for i in range(140):
        # Create price trend with slight oscillation
        if i < 70:
            price = base_price + (i * 10)
        else:
            price = base_price + 700 - ((i - 70) * 15)

        candles.append({
            "symbol": "BTCUSDT",
            "interval": "1m",
            "open_time": t0 + timedelta(minutes=i),
            "close_time": t0 + timedelta(minutes=i, seconds=59),
            "open": price,
            "high": price + 5.0,
            "low": price - 5.0,
            "close": price + 2.0,
            "volume": 20.0,
            "quote_volume": price * 20.0,
            "trades_count": 40,
            "is_closed": True,
            "source": "api_test",
            "ingested_at": datetime.now(timezone.utc),
        })

    await market_service.save_candles(test_session, candles)

    # 2. POST /api/v1/backtests
    post_res = await client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "trend_following",
            "symbol": "BTCUSDT",
            "interval": "1m",
            "initial_cash": 10000.0,
            "parameters": {
                "fast_window": 10,
                "slow_window": 30,
            },
            "cost_assumptions": {
                "maker_fee_bps": 8.0,
                "taker_fee_bps": 12.0,
                "slippage_bps": 6.0,
            },
        },
    )
    assert post_res.status_code == 201, post_res.text
    data = post_res.json()
    run_id = data["id"]
    assert run_id is not None
    assert data["strategy_id"] == "trend_following"
    assert data["symbol"] == "BTCUSDT"
    assert data["status"] == "completed"
    assert "metrics" in data
    assert "equity_curve" in data
    assert len(data["equity_curve"]) > 0
    assert "regime_performance" in data
    assert "stress_test_results" in data
    assert data["dataset_fingerprint"] is not None

    # 3. GET /api/v1/backtests/{run_id}
    get_res = await client.get(f"/api/v1/backtests/{run_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == run_id
    assert get_data["candle_count"] >= 100
    assert len(get_data["equity_curve"]) == len(data["equity_curve"])

    # 4. GET /api/v1/backtests (list)
    list_res = await client.get("/api/v1/backtests?strategy_id=trend_following")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["count"] >= 1
    found_ids = [b["id"] for b in list_data["backtests"]]
    assert run_id in found_ids

    # 5. GET /api/v1/backtests/{invalid_id} -> 404
    not_found_res = await client.get("/api/v1/backtests/invalid-uuid-0000")
    assert not_found_res.status_code == 404

    # 6. GET /api/v1/analytics/performance
    analytics_res = await client.get("/api/v1/analytics/performance")
    assert analytics_res.status_code == 200
    perf = analytics_res.json()
    assert perf["total_backtests"] >= 1
    assert "avg_sharpe_ratio" in perf
    assert len(perf["runs"]) >= 1
