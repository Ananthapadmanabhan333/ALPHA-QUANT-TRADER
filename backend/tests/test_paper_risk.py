"""
Unit tests for ALPHA Quant Phase 5 Central Risk Gate & Pre-Trade Invariants:
- Live trading forbidden safety invariant
- Order notional limit
- Position size concentration limit (10% virtual equity)
- Portfolio exposure limit (80% virtual equity)
- Daily loss threshold and peak-to-trough drawdown limits
- Consecutive loss streak limit
- Stale feed detection
- Spread filter
- Emergency stop & resume
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAccount, PaperPosition, PaperRiskState
from app.paper.constants import OrderSide, OrderType
from app.paper.exceptions import (
    EmergencyStopActiveException,
    InvalidOrderException,
    LiveTradingForbiddenException,
    RiskBreachException,
    StaleFeedException,
)
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest


@pytest.fixture
def risk_gate():
    return CentralRiskGate()


def test_live_trading_security_invariant_rejected(risk_gate: CentralRiskGate):
    """
    Security Invariant: Any configuration or payload specifying live execution is strictly rejected.
    """
    with pytest.raises(ValueError) as exc_info:
        PaperOrderCreateRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=0.01,
            is_live=True,  # LIVE TRADING ATTEMPT
        )
    assert "Live trading is strictly prohibited" in str(exc_info.value)


def test_max_order_notional_breach(risk_gate: CentralRiskGate):
    account = PaperAccount(virtual_balance=50000.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        starting_daily_equity=50000.0,
        peak_equity=50000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    # 1.0 BTC @ 50,000 = $50,000 > max order notional $10,000
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc_info.value.rule_name == "MAX_ORDER_NOTIONAL"


def test_max_position_concentration_breach(risk_gate: CentralRiskGate):
    # Total virtual equity = $10,000. Max position 10% = $1,000.
    # Order for 0.03 BTC @ 50,000 = $1,500 (> $1,000).
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.10,
        max_portfolio_exposure_pct=0.80,
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.03,  # $1,500 notional
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc_info.value.rule_name == "MAX_POSITION_CONCENTRATION"


def test_daily_loss_limit_breach(risk_gate: CentralRiskGate):
    # Starting daily equity = $10,000. Daily loss limit 2% = -$200.
    # Current daily loss = -$250.
    account = PaperAccount(virtual_balance=9750.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        daily_loss_limit_pct=0.02,
        starting_daily_equity=10000.0,
        current_daily_pnl=-250.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc_info.value.rule_name == "DAILY_LOSS_LIMIT"
    assert risk_state.emergency_stop is True


def test_max_drawdown_limit_breach(risk_gate: CentralRiskGate):
    # Peak equity = $10,000. Max DD = 5%.
    # Current equity = $9,400 (6% DD > 5%).
    account = PaperAccount(virtual_balance=9400.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        max_drawdown_limit_pct=0.05,
        starting_daily_equity=9400.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc_info.value.rule_name == "MAX_DRAWDOWN_LIMIT"
    assert risk_state.emergency_stop is True


def test_consecutive_losses_limit_breach(risk_gate: CentralRiskGate):
    # Consecutive loss limit = 3. Current consecutive losses = 3.
    account = PaperAccount(virtual_balance=9900.0)  # 1% DD (< 5% max DD limit)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        max_drawdown_limit_pct=0.05,
        consecutive_loss_limit=3,
        consecutive_losses=3,
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc_info.value.rule_name == "CONSECUTIVE_LOSS_LIMIT"


def test_stale_market_feed_detection(risk_gate: CentralRiskGate):
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    # Feed is 600 seconds old (> 300s max threshold)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=600)

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(StaleFeedException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=stale_time,
        )
    assert "Market feed for BTCUSDT is stale" in str(exc_info.value)


def test_emergency_stop_halts_new_entries(risk_gate: CentralRiskGate):
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        emergency_stop=True,
        kill_switch_reason="Manual emergency halt by compliance officer",
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    with pytest.raises(EmergencyStopActiveException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert "Emergency Stop active" in str(exc_info.value)


def test_excessive_spread_filter(risk_gate: CentralRiskGate):
    account = PaperAccount(virtual_balance=10000.0)
    risk_state = PaperRiskState(
        starting_daily_equity=10000.0,
        peak_equity=10000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        current_market_price=50000.0,
    )

    # Spread is 80 bps (> 50 bps limit)
    with pytest.raises(RiskBreachException) as exc_info:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
            spread_bps=80.0,
        )
    assert exc_info.value.rule_name == "EXCESSIVE_SPREAD"
