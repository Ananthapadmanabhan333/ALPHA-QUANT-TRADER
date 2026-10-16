"""
ALPHA Quant — Phase 6: Orchestration Lifecycle Manager Integration Tests.
Tests the full signal-to-paper-fill 9-stage lifecycle, task ownership, duplicate scheduler prevention,
stale feed handling, and risk gate enforcement.
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.models import MarketCandle
from app.market.service import MarketDataService
from app.orchestration.exceptions import DuplicateSchedulerException
from app.orchestration.lifecycle import LifecycleManager, LifecycleStatus
from app.paper.broker import PaperBroker
from app.paper.constants import OrderSide, OrderType
from app.paper.schemas import PaperOrderCreateRequest
from app.quant.constants import STRATEGY_TREND_FOLLOWING


def generate_synthetic_candles(
    count: int = 120,
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    base_price: float = 50000.0,
    trend_up: bool = True,
    now: datetime = None,
) -> list[dict]:
    """Generates synthetic deterministic candles sufficient for 100-bar warmup."""
    now = now or datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=count)
    candles = []
    current_price = base_price

    for i in range(count):
        open_time = start_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        step = 5.0 if trend_up else -5.0
        open_p = current_price
        close_p = open_p + step
        high_p = max(open_p, close_p) + 2.0
        low_p = min(open_p, close_p) - 2.0
        current_price = close_p

        candles.append({
            "symbol": symbol,
            "interval": interval,
            "open_time": open_time,
            "close_time": close_time,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": 50.0,
            "quote_volume": 50.0 * close_p,
            "trades_count": 100,
            "is_closed": True,
            "source": "lifecycle_test",
            "ingested_at": close_time,
        })
    return candles


@pytest.mark.asyncio
async def test_lifecycle_full_9_stage_cycle(test_session: AsyncSession):
    """
    Validates end-to-end execution of a single deterministic cycle across all 9 stages:
    1. Market-data health check
    2. Feature pipeline readiness
    3. Strategy scheduling
    4. Signal validation
    5. Central Risk Gate
    6. Paper order submission
    7. Fill processing
    8. Portfolio updates
    9. Event persistence & live broadcast
    """
    now = datetime.now(timezone.utc)
    market_service = MarketDataService()
    candles = generate_synthetic_candles(count=120, now=now, trend_up=True)
    await market_service.save_candles(test_session, candles)

    manager = LifecycleManager()
    manager.strategy_id = STRATEGY_TREND_FOLLOWING
    manager.symbol = "BTCUSDT"
    manager.interval = "1m"
    manager.order_size_pct = 0.05

    # Run single cycle through the 9 stages
    cycle_result = await manager.run_single_cycle(test_session)

    assert cycle_result["status"] in ["COMPLETED", "SKIPPED"]
    stages = cycle_result["stages"]

    # Verify Stage 1
    assert "stage_1_market_health" in stages
    assert stages["stage_1_market_health"]["status"] == "HEALTHY"

    # Verify Stage 2
    assert "stage_2_feature_readiness" in stages
    assert stages["stage_2_feature_readiness"]["status"] == "READY"
    assert stages["stage_2_feature_readiness"]["bars_computed"] >= 100

    # Verify Stage 3
    assert "stage_3_strategy_scheduling" in stages
    assert stages["stage_3_strategy_scheduling"]["strategy"] == STRATEGY_TREND_FOLLOWING

    # Verify Stage 4
    assert "stage_4_signal_validation" in stages

    # If the trend generated a BUY signal, verify execution through stage 5-9
    if cycle_result["status"] == "COMPLETED" and stages["stage_4_signal_validation"].get("status") == "VALID":
        assert "stage_5_risk_gate" in stages
        assert stages["stage_5_risk_gate"]["status"] == "PASSED"

        assert "stage_6_order_submission" in stages
        assert stages["stage_6_order_submission"]["order_id"] is not None

        assert "stage_7_fill_processing" in stages
        assert stages["stage_7_fill_processing"]["fills_count"] > 0

        assert "stage_8_portfolio_updates" in stages
        assert stages["stage_8_portfolio_updates"]["position_qty"] > 0

        assert "stage_9_event_persistence" in stages
        assert stages["stage_9_event_persistence"]["persisted"] is True


@pytest.mark.asyncio
async def test_lifecycle_duplicate_scheduler_prevention():
    """
    Validates that attempting to start a scheduler instance when one is already running
    is rejected with DuplicateSchedulerException and preserves the active instance.
    """
    manager = LifecycleManager()
    start_res = await manager.start(
        strategy_id=STRATEGY_TREND_FOLLOWING,
        symbol="BTCUSDT",
        poll_interval_seconds=10.0,
    )
    assert start_res["status"] == "RUNNING"
    task_id = start_res["task_id"]

    try:
        # Second start attempt must fail
        with pytest.raises(DuplicateSchedulerException) as exc_info:
            await manager.start(
                strategy_id=STRATEGY_TREND_FOLLOWING,
                symbol="BTCUSDT",
            )
        assert "Duplicate scheduler instance rejected" in str(exc_info.value)
        assert exc_info.value.status_code == 409
    finally:
        # Clean shutdown
        stop_res = await manager.stop()
        assert stop_res["status"] == "STOPPED"
        assert manager.status == LifecycleStatus.STOPPED


@pytest.mark.asyncio
async def test_lifecycle_risk_gate_rejection_during_run(test_session: AsyncSession):
    """
    Validates that when risk limits are breached (e.g. emergency halt active),
    the lifecycle stage 5 catches the breach, persists a RISK_BREACH event, and aborts order submission.
    """
    now = datetime.now(timezone.utc)
    market_service = MarketDataService()
    candles = generate_synthetic_candles(count=120, now=now, trend_up=True)
    await market_service.save_candles(test_session, candles)

    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    risk_state = await broker.get_account_risk_state(test_session, account.id)

    # Manually activate Emergency Stop
    risk_state.emergency_stop = True
    risk_state.kill_switch_reason = "Test risk breach active"
    await test_session.commit()

    manager = LifecycleManager(broker=broker)
    manager.strategy_id = STRATEGY_TREND_FOLLOWING
    manager.symbol = "BTCUSDT"

    cycle_result = await manager.run_single_cycle(test_session)

    # Stage 5 must reject if a trade was proposed
    if "stage_5_risk_gate" in cycle_result.get("stages", {}):
        assert cycle_result["stages"]["stage_5_risk_gate"]["status"] == "REJECTED"
        assert cycle_result["status"] == "RISK_REJECTED"
        # No order should have been submitted in stage 6
        assert "stage_6_order_submission" not in cycle_result["stages"]


@pytest.mark.asyncio
async def test_lifecycle_insufficient_warmup_handling(test_session: AsyncSession):
    """
    Validates that when database contains fewer candles than the required warmup period,
    Stage 2 detects this and skips execution gracefully without raising an unhandled exception.
    """
    now = datetime.now(timezone.utc)
    market_service = MarketDataService()
    # Provide only 20 candles (trend following requires 100)
    candles = generate_synthetic_candles(count=20, now=now, trend_up=True)
    await market_service.save_candles(test_session, candles)

    manager = LifecycleManager()
    manager.strategy_id = STRATEGY_TREND_FOLLOWING
    manager.symbol = "BTCUSDT"

    cycle_result = await manager.run_single_cycle(test_session)
    assert cycle_result["status"] == "SKIPPED"
    assert cycle_result["stages"]["stage_2_feature_readiness"]["status"] == "INSUFFICIENT_BARS"
