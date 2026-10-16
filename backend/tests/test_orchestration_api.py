"""
ALPHA Quant — Phase 6: Orchestration, Portfolio, Risk, and Security API Tests.
Validates all Phase 6 REST endpoints:
- GET /health and GET /ready (readiness failure if dependencies down)
- GET /api/v1/portfolio
- GET /api/v1/orders (paginated)
- GET /api/v1/fills (paginated)
- GET /api/v1/risk/status
- GET /api/v1/events (paginated)
- POST /api/v1/paper-trading/start & POST /api/v1/paper-trading/stop
- POST /api/v1/risk/reset
- GET /api/v1/tasks/{task_id}
- Authentication & Authorization enforcement
- Paper-only invariant verification
"""

from datetime import datetime, timezone
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.market.service import MarketDataService
from app.orchestration.lifecycle import get_lifecycle_manager


@pytest.mark.asyncio
async def test_api_readiness_dependency_checks(client: AsyncClient):
    """
    Validates that /ready checks both database and market data dependencies.
    """
    res = await client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert "components" in data
    assert "database" in data["components"]
    assert "market_data" in data["components"]
    assert data["components"]["database"]["connected"] is True
    assert data["components"]["market_data"]["connected"] is True


@pytest.mark.asyncio
async def test_api_readiness_failure_when_dependency_down(test_app, client: AsyncClient):
    """
    Validates requirement: A service must not report readiness if its required database
    or market-data dependencies are unavailable.
    """
    from app.market.rest_adapter import BinanceRestAdapter

    # Inject simulated outage on market data adapter
    BinanceRestAdapter._global_mock_status = {
        "status": "unhealthy",
        "connected": False,
        "error": "Simulated upstream exchange timeout",
    }
    try:
        res = await client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["ready"] is False
        assert data["components"]["market_data"]["connected"] is False
    finally:
        BinanceRestAdapter._global_mock_status = None


@pytest.mark.asyncio
async def test_api_portfolio_and_ledgers(client: AsyncClient, test_session: AsyncSession):
    """
    Validates GET /api/v1/portfolio, GET /api/v1/orders, GET /api/v1/fills, GET /api/v1/risk/status.
    """
    # Seed fresh candle so feed status is healthy
    market_service = MarketDataService()
    now = datetime.now(timezone.utc)
    candle = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "open_time": now,
        "close_time": now,
        "open": 50000.0,
        "high": 50100.0,
        "low": 49900.0,
        "close": 50050.0,
        "volume": 100.0,
        "quote_volume": 5000000.0,
        "trades_count": 500,
        "is_closed": True,
        "source": "api_test",
        "ingested_at": now,
    }
    await market_service.save_candles(test_session, [candle])

    # 1. GET /api/v1/portfolio
    port_res = await client.get("/api/v1/portfolio?symbol=BTCUSDT")
    assert port_res.status_code == 200
    port_data = port_res.json()
    assert port_data["virtual_balance"] == 10000.0
    assert port_data["total_equity"] == 10000.0
    assert "positions" in port_data

    # 2. GET /api/v1/orders (paginated)
    orders_res = await client.get("/api/v1/orders?limit=10&offset=0")
    assert orders_res.status_code == 200
    orders_data = orders_res.json()
    assert "total" in orders_data
    assert "limit" in orders_data
    assert "offset" in orders_data
    assert "items" in orders_data
    assert isinstance(orders_data["items"], list)

    # 3. GET /api/v1/fills (paginated)
    fills_res = await client.get("/api/v1/fills?limit=10&offset=0")
    assert fills_res.status_code == 200
    fills_data = fills_res.json()
    assert "total" in fills_data
    assert "items" in fills_data
    assert isinstance(fills_data["items"], list)

    # 4. GET /api/v1/risk/status
    risk_res = await client.get("/api/v1/risk/status?symbol=BTCUSDT")
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["emergency_stop"] is False
    assert risk_data["is_trading_allowed"] is True
    assert risk_data["daily_loss_limit_pct"] == 2.0


@pytest.mark.asyncio
async def test_api_events_paginated(client: AsyncClient):
    """
    Validates GET /api/v1/events with pagination and query filters.
    """
    res = await client.get("/api/v1/events?limit=25&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_api_auth_protection_on_mutating_endpoints(test_app, client: AsyncClient):
    """
    Validates that when settings.REQUIRE_AUTH is True, mutating operations
    require valid X-API-Key or Bearer token, and reject unauthorized requests with 401.
    """
    from app.core.config import get_settings

    auth_settings = Settings(
        ENVIRONMENT="testing",
        ADMIN_API_KEY="secret-admin-passkey",
        REQUIRE_AUTH=True,
    )
    test_app.dependency_overrides[get_settings] = lambda: auth_settings
    try:
        payload = {
            "strategy_id": "trend_following",
            "symbol": "BTCUSDT",
            "interval": "1m",
            "poll_interval_seconds": 10.0,
        }

        # 1. Unauthenticated request -> must return 401
        res_no_auth = await client.post("/api/v1/paper-trading/start", json=payload)
        assert res_no_auth.status_code == 401
        assert "Unauthorized" in res_no_auth.json()["error"]["message"]

        # 2. Invalid API key -> must return 401
        res_bad_key = await client.post(
            "/api/v1/paper-trading/start",
            json=payload,
            headers={"X-API-Key": "wrong-key"},
        )
        assert res_bad_key.status_code == 401

        # 3. Valid API key -> must pass authentication
        res_valid_key = await client.post(
            "/api/v1/paper-trading/start",
            json=payload,
            headers={"X-API-Key": "secret-admin-passkey"},
        )
        assert res_valid_key.status_code == 200
        assert res_valid_key.json()["status"] == "RUNNING"

        # Stop paper trading with valid auth
        res_stop = await client.post(
            "/api/v1/paper-trading/stop",
            headers={"X-API-Key": "secret-admin-passkey"},
        )
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "STOPPED"
    finally:
        test_app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_api_risk_reset(client: AsyncClient, test_session: AsyncSession):
    """
    Validates POST /api/v1/risk/reset allows operators to reset tripped controls
    using the mandatory 'CONFIRM_RESET' confirmation code.
    """
    # Trigger emergency stop first
    halt_res = await client.post(
        "/api/v1/paper/risk/emergency-stop",
        json={"reason": "Manual operator halt for test"},
    )
    assert halt_res.status_code == 200
    assert halt_res.json()["emergency_stop"] is True

    # 1. Attempt reset with invalid confirmation code
    bad_reset = await client.post(
        "/api/v1/risk/reset",
        json={"confirmation_code": "WRONG_TOKEN"},
    )
    assert bad_reset.status_code in [400, 422]

    # 2. Reset with correct confirmation code 'CONFIRM_RESET'
    good_reset = await client.post(
        "/api/v1/risk/reset",
        json={
            "confirmation_code": "CONFIRM_RESET",
            "reset_emergency_stop": True,
            "reset_consecutive_losses": True,
            "reason": "Test risk reset",
        },
    )
    assert good_reset.status_code == 200
    reset_data = good_reset.json()
    assert reset_data["success"] is True
    assert reset_data["risk_state"]["emergency_stop"] is False


@pytest.mark.asyncio
async def test_api_async_backtest_task_queue(client: AsyncClient, test_session: AsyncSession):
    """
    Validates background task queue execution for long-running backtests:
    POST /api/v1/backtests?async_mode=true -> 202 Accepted with task_id.
    GET /api/v1/tasks/{task_id} -> Query task execution status.
    """
    now = datetime.now(timezone.utc)
    market_service = MarketDataService()
    # Seed 120 candles so backtest succeeds
    from tests.test_orchestration_lifecycle import generate_synthetic_candles
    candles = generate_synthetic_candles(count=120, now=now, trend_up=True)
    await market_service.save_candles(test_session, candles)

    payload = {
        "strategy_id": "trend_following",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "start_time": (now - datetime.fromtimestamp(120 * 60, tz=timezone.utc)).isoformat() if False else None,
        "initial_capital": 10000.0,
    }

    # Execute with async_mode=true
    post_res = await client.post("/api/v1/backtests?async_mode=true", json=payload)
    assert post_res.status_code == 202
    task_data = post_res.json()
    assert "task_id" in task_data
    task_id = task_data["task_id"]
    assert task_data["task_type"] == "BACKTEST_SIMULATION"

    # Query task status via GET /api/v1/tasks/{task_id}
    status_res = await client.get(f"/api/v1/tasks/{task_id}")
    assert status_res.status_code == 200
    query_data = status_res.json()
    assert query_data["task_id"] == task_id
    assert query_data["status"] in ["PENDING", "RUNNING", "COMPLETED"]


@pytest.mark.asyncio
async def test_api_reject_live_trading_invariant(client: AsyncClient):
    """
    Validates that setting is_live=True is rejected across paper trading endpoints.
    """
    payload = {
        "strategy_id": "trend_following",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "is_live": True,
    }
    res = await client.post("/api/v1/paper-trading/start", json=payload)
    assert res.status_code == 422
    assert "Live trading is strictly prohibited" in res.text
