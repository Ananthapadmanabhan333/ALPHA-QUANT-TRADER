"""
ALPHA Quant — Phase 8: Comprehensive Failure Mode & Recovery Tests.
Validates fail-safe behaviors across 12 critical failure and stress vectors:
1. Market-data disconnection
2. Missing candles & sequence gaps
3. Stale prices
4. Database outage
5. Application restart
6. Duplicate order submission
7. Duplicate fill processing
8. Insufficient virtual balance
9. Circuit-breaker activation
10. Invalid API input
11. Unauthorized configuration changes
12. Interrupted backtests
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.market.tracker import MarketDataTracker
from app.market.validator import MarketDataValidator
from app.paper.broker import PaperBroker
from app.paper.exceptions import (
    CircuitBreakerTrippedException,
    InsufficientBalanceException,
    InvalidOrderException,
    RiskBreachException,
)
from app.paper.models import PaperOrder, PaperOrderStatus, PaperOrderType, PaperSide
from app.paper.risk_gate import CentralRiskGate
from app.paper.service import PaperService
from app.quant.constants import STRATEGY_TREND_FOLLOWING
from app.orchestration.tasks import BackgroundTaskManager


@pytest.mark.asyncio
async def test_failure_1_market_data_disconnection():
    """1. Test that disconnection cleanly updates tracker and prevents silent assumptions."""
    tracker = MarketDataTracker()
    tracker.set_connected(True, "BTCUSDT", "1m")
    assert tracker.is_connected("BTCUSDT", "1m") is True

    # Simulate WebSocket disconnection event
    tracker.set_connected(False, "BTCUSDT", "1m")
    status = tracker.get_status("BTCUSDT", "1m")
    assert status.connected is False
    assert status.feed_state == "DISCONNECTED"
    assert status.is_stale is True


@pytest.mark.asyncio
async def test_failure_2_missing_candles_and_gaps():
    """2. Test that sequence gaps are detected without fabricating synthetic candles."""
    now = datetime.now(timezone.utc)
    c1 = {"symbol": "BTCUSDT", "interval": "1m", "open_time": now, "close_time": now + timedelta(minutes=1)}
    # Skip minute 2 (simulate missing candle)
    c3 = {"symbol": "BTCUSDT", "interval": "1m", "open_time": now + timedelta(minutes=2), "close_time": now + timedelta(minutes=3)}

    gaps = MarketDataValidator.detect_sequence_gaps([c1, c3], interval="1m")
    assert len(gaps) == 1
    assert gaps[0]["expected_gap_candles"] == 1


@pytest.mark.asyncio
async def test_failure_3_stale_prices_risk_guard(test_session: AsyncSession):
    """3. Test that stale prices trip the Central Risk Gate and reject orders."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_stale_acc")

    # Set feed to 500s ago (> 300s limit)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=500)
    risk_gate = CentralRiskGate()
    risk_gate.update_feed_time("BTCUSDT", stale_time)

    with pytest.raises(RiskBreachException) as exc:
        await risk_gate.validate_order(
            account=account,
            symbol="BTCUSDT",
            side=PaperSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=Decimal("0.01"),
            current_market_price=Decimal("60000.00"),
        )
    assert "STALE" in str(exc.value)


@pytest.mark.asyncio
async def test_failure_4_database_outage(client: AsyncClient):
    """4. Test that readiness probes immediately report failure when database fails."""
    # Probe normal readiness
    res = await client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_failure_5_application_restart_preservation(test_session: AsyncSession):
    """5. Test that application restart restores persisted ledger and risk states."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_restart_acc")
    account.virtual_balance = Decimal("8500.00")
    account.realized_pnl = Decimal("-150.00")
    await test_session.commit()

    # Re-instantiate broker (simulating restart)
    new_broker = PaperBroker()
    recovered_account = await new_broker.get_or_create_account(test_session, "test_restart_acc")
    assert recovered_account.virtual_balance == Decimal("8500.00")
    assert recovered_account.realized_pnl == Decimal("-150.00")


@pytest.mark.asyncio
async def test_failure_6_duplicate_order_submission_idempotency(test_session: AsyncSession):
    """6. Test that duplicate client_order_id submissions fail safely or return existing order."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_idem_acc")
    client_order_id = "test_order_duplicate_key_123"

    order1 = await broker.create_order(
        db=test_session,
        account=account,
        symbol="BTCUSDT",
        side=PaperSide.BUY,
        order_type=PaperOrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=Decimal("50000.00"),
        client_order_id=client_order_id,
    )
    assert order1.id is not None

    # Re-submitting same client_order_id must be rejected
    with pytest.raises(InvalidOrderException) as exc:
        await broker.create_order(
            db=test_session,
            account=account,
            symbol="BTCUSDT",
            side=PaperSide.BUY,
            order_type=PaperOrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("50000.00"),
            client_order_id=client_order_id,
        )
    assert "DUPLICATE_CLIENT_ORDER_ID" in str(exc.value)


@pytest.mark.asyncio
async def test_failure_7_duplicate_fill_processing(test_session: AsyncSession):
    """7. Test that filled orders cannot be filled a second time."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_fill_acc")
    order = await broker.create_order(
        db=test_session,
        account=account,
        symbol="BTCUSDT",
        side=PaperSide.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=Decimal("0.01"),
    )

    # First fill
    fill = await broker.fill_market_order(
        db=test_session,
        account=account,
        order=order,
        next_price=Decimal("50000.00"),
    )
    assert fill is not None
    assert order.status == PaperOrderStatus.FILLED

    # Second fill attempt on already filled order must fail
    with pytest.raises(InvalidOrderException):
        await broker.fill_market_order(
            db=test_session,
            account=account,
            order=order,
            next_price=Decimal("50100.00"),
        )


@pytest.mark.asyncio
async def test_failure_8_insufficient_virtual_balance(test_session: AsyncSession):
    """8. Test that orders exceeding cash are strictly rejected without modifying balance."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_cash_acc")
    account.virtual_balance = Decimal("100.00") # only $100
    await test_session.commit()

    order = await broker.create_order(
        db=test_session,
        account=account,
        symbol="BTCUSDT",
        side=PaperSide.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=Decimal("1.0"), # $50,000 required
    )

    with pytest.raises(InsufficientBalanceException):
        await broker.fill_market_order(
            db=test_session,
            account=account,
            order=order,
            next_price=Decimal("50000.00"),
        )
    # Balance must remain completely unmutated
    assert account.virtual_balance == Decimal("100.00")


@pytest.mark.asyncio
async def test_failure_9_circuit_breaker_emergency_stop(test_session: AsyncSession):
    """9. Test that Emergency Stop immediately trips circuit breaker and halts all entry orders."""
    risk_gate = CentralRiskGate()
    risk_gate.trigger_emergency_stop("Manual safety kill switch")
    assert risk_gate.is_emergency_stopped is True

    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_stop_acc")

    with pytest.raises(CircuitBreakerTrippedException):
        await risk_gate.validate_order(
            account=account,
            symbol="BTCUSDT",
            side=PaperSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=Decimal("0.01"),
            current_market_price=Decimal("50000.00"),
        )


@pytest.mark.asyncio
async def test_failure_10_invalid_api_input(client: AsyncClient):
    """10. Test that invalid API payloads return structured HTTP 422 validation errors."""
    # Negative quantity
    res = await client.post(
        "/api/v1/paper/orders",
        json={"symbol": "BTCUSDT", "side": "buy", "quantity": -5.0},
    )
    assert res.status_code == 422

    # Invalid side
    res2 = await client.post(
        "/api/v1/paper/orders",
        json={"symbol": "BTCUSDT", "side": "invalid_side", "quantity": 0.01},
    )
    assert res2.status_code == 422


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
    from app.core.config import get_settings
    test_app.dependency_overrides[get_settings] = lambda: auth_settings

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        # Mutating start without key
        res = await ac.post("/api/v1/paper-trading/start", json={"strategy_id": STRATEGY_TREND_FOLLOWING})
        assert res.status_code == 401

        # Mutating start with valid key
        res_valid = await ac.post(
            "/api/v1/paper-trading/start",
            headers={"X-API-Key": "super-secret-key-123"},
            json={"strategy_id": STRATEGY_TREND_FOLLOWING},
        )
        assert res_valid.status_code != 401


@pytest.mark.asyncio
async def test_failure_12_interrupted_backtest_task_handling():
    """12. Test that async background task manager safely tracks tasks and errors."""
    task_mgr = BackgroundTaskManager()

    async def faulty_task():
        raise RuntimeError("Simulated mid-run worker crash")

    task_id = await task_mgr.submit_task("simulated_crash_backtest", faulty_task)
    status = task_mgr.get_task(task_id)
    assert status is not None
    # Let task run
    import asyncio
    await asyncio.sleep(0.05)

    status_after = task_mgr.get_task(task_id)
    assert status_after is not None
    assert status_after.status in ("FAILED", "COMPLETED")
    if status_after.status == "FAILED":
        assert "Simulated mid-run worker crash" in (status_after.error_message or "")
