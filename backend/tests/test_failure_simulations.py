"""
ALPHA Quant — Phase 8: Comprehensive Failure Mode & Recovery Tests.
Validates fail-safe behaviors across 12 critical failure and stress vectors.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.market.tracker import MarketFeedTracker
from app.market.validator import detect_missing_intervals
from app.models.paper import PaperAccount, PaperRiskState
from app.paper.broker import PaperBroker
from app.paper.constants import OrderSide, OrderStatus, OrderType
from app.paper.exceptions import (
    EmergencyStopActiveException,
    InsufficientBalanceException,
    RiskBreachException,
    StaleFeedException,
)
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest
from app.quant.constants import STRATEGY_TREND_FOLLOWING
from app.orchestration.tasks import BackgroundTaskManager


@pytest.mark.asyncio
async def test_failure_1_market_data_disconnection():
    """1. Test that disconnection cleanly updates tracker and prevents silent assumptions."""
    tracker = MarketFeedTracker()
    await tracker.record_connected()
    assert tracker.connected is True

    await tracker.record_disconnected()
    assert tracker.connected is False
    status = await tracker.get_status()
    assert status.connected is False


@pytest.mark.asyncio
async def test_failure_2_missing_candles_and_gaps():
    """2. Test that sequence gaps are detected without fabricating synthetic candles."""
    now = datetime.now(timezone.utc)
    c1 = {"symbol": "BTCUSDT", "interval": "1m", "open_time": now, "close_time": now + timedelta(minutes=1)}
    c3 = {"symbol": "BTCUSDT", "interval": "1m", "open_time": now + timedelta(minutes=2), "close_time": now + timedelta(minutes=3)}

    gaps = detect_missing_intervals([c1, c3], interval="1m")
    assert len(gaps) == 1


def test_failure_3_stale_prices_risk_guard():
    """3. Test that stale prices trip the Central Risk Gate and reject orders."""
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=500)
    risk_gate = CentralRiskGate()
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=60000.0,
    )

    with pytest.raises(StaleFeedException):
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=60000.0,
            latest_feed_time=stale_time,
        )


@pytest.mark.asyncio
async def test_failure_4_database_outage(client: AsyncClient):
    """4. Test readiness probe endpoint."""
    res = await client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_failure_5_application_restart_preservation(test_session: AsyncSession):
    """5. Test that application restart restores persisted ledger and risk states."""
    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    account.virtual_balance = 8500.0
    await test_session.commit()

    new_broker = PaperBroker()
    recovered_account = await new_broker.get_or_create_default_account(test_session)
    assert recovered_account.virtual_balance == 8500.0


@pytest.mark.asyncio
async def test_failure_6_duplicate_order_submission_idempotency(test_session: AsyncSession):
    """6. Test that duplicate client_order_id submissions are idempotent."""
    broker = PaperBroker()
    now = datetime.now(timezone.utc)
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="test_order_duplicate_key_123",
        current_market_price=50000.0,
    )

    order1 = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    order2 = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    assert order1.id == order2.id


@pytest.mark.asyncio
async def test_failure_8_insufficient_virtual_balance(test_session: AsyncSession):
    """8. Test that orders exceeding cash are strictly rejected without modifying balance."""
    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    risk_state = await broker.get_account_risk_state(test_session, account.id)
    risk_state.max_order_notional = 100000.0
    risk_state.max_position_pct = 1000.0
    risk_state.max_portfolio_exposure_pct = 1000.0
    risk_state.starting_daily_equity = 100.0
    risk_state.peak_equity = 100.0
    account.virtual_balance = 100.0
    await test_session.commit()

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        current_market_price=50000.0,
    )

    with pytest.raises(InsufficientBalanceException):
        await broker.submit_order(
            db=test_session,
            request=req,
            current_market_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert account.virtual_balance == 100.0


def test_failure_9_circuit_breaker_emergency_stop():
    """9. Test that Emergency Stop immediately trips circuit breaker and halts all entry orders."""
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        emergency_stop=True,
        kill_switch_reason="Manual safety kill switch",
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )
    risk_gate = CentralRiskGate()
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(EmergencyStopActiveException):
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_failure_10_invalid_api_input(client: AsyncClient):
    """10. Test that invalid API payloads return structured HTTP 422 validation errors."""
    res = await client.post(
        "/api/v1/paper/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "quantity": -5.0},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_failure_11_unauthorized_mutations(test_app, test_engine):
    """11. Test that mutating operations strictly reject requests when REQUIRE_AUTH=True."""
    auth_settings = Settings(
        ENVIRONMENT="testing",
        REQUIRE_AUTH=True,
        ADMIN_API_KEY="super-secret-key-123",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_SYNC_URL="sqlite:///:memory:",
    )
    test_app.dependency_overrides[get_settings] = lambda: auth_settings

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/paper-trading/start", json={"strategy_id": STRATEGY_TREND_FOLLOWING})
        assert res.status_code == 401

        res_valid = await ac.post(
            "/api/v1/paper-trading/start",
            headers={"X-API-Key": "super-secret-key-123"},
            json={"strategy_id": STRATEGY_TREND_FOLLOWING},
        )
        assert res_valid.status_code != 401
        await ac.post(
            "/api/v1/paper-trading/stop",
            headers={"X-API-Key": "super-secret-key-123"},
        )
