"""
ALPHA Quant — Phase 8: Automated Security Invariants & Compliance Audit Tests.
Verifies critical security and non-execution invariants.
"""

from datetime import datetime, timezone
import os
import pytest
from httpx import AsyncClient

import app
from app.core.config import get_settings
from app.db.base import Base
from app.models.paper import PaperAccount, PaperRiskState
from app.paper.constants import OrderSide, OrderType
from app.paper.exceptions import RiskBreachException
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest


def test_security_invariant_1_no_live_trading_client():
    """Verify that no live trading exchange client or execution gateway exists."""
    app_dir = os.path.dirname(app.__file__)
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                    assert "create_withdrawal" not in content.lower()
                    assert "wallet_withdraw" not in content.lower()
                    assert "binance_secret" not in content.lower()


def test_security_invariant_2_database_tables_are_strictly_paper():
    """Verify that all financial models in SQLAlchemy are strictly paper/simulated."""
    table_names = list(Base.metadata.tables.keys())
    assert "paper_accounts" in table_names
    assert "paper_orders" in table_names
    assert "paper_fills" in table_names
    assert "paper_positions" in table_names

    for name in table_names:
        assert "live_account" not in name
        assert "exchange_credential" not in name
        assert "api_key_store" not in name
        assert "wallet" not in name


def test_security_invariant_3_frontend_cannot_bypass_risk_gate():
    """Verify that order submission always passes through the Central Risk Gate."""
    account = PaperAccount(virtual_balance=50000.0)
    risk_state = PaperRiskState(
        max_order_notional=10000.0,
        max_position_pct=0.50,
        max_portfolio_exposure_pct=0.80,
        starting_daily_equity=50000.0,
        peak_equity=50000.0,
        last_daily_reset=datetime.now(timezone.utc),
    )
    risk_gate = CentralRiskGate()
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.3,
        current_market_price=50000.0,
    )

    with pytest.raises(RiskBreachException) as exc:
        risk_gate.check_pre_trade_invariants(
            request=req,
            account=account,
            risk_state=risk_state,
            current_position=None,
            current_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )
    assert exc.value.rule_name == "MAX_ORDER_NOTIONAL"


@pytest.mark.asyncio
async def test_security_invariant_4_no_live_order_routes(client: AsyncClient):
    """Verify that attempting to call live execution routes returns HTTP 404."""
    routes_to_probe = [
        "/api/v1/orders/live",
        "/api/v1/trade/live",
        "/api/v1/exchange/order",
        "/api/v1/withdraw",
        "/api/v1/binance/order",
    ]
    for route in routes_to_probe:
        res = await client.post(route, json={"symbol": "BTCUSDT", "quantity": 1})
        assert res.status_code == 404


def test_security_invariant_5_settings_zero_hardcoded_secrets():
    """Verify default Settings does not commit production secrets or live credentials."""
    settings = get_settings()
    assert not hasattr(settings, "BINANCE_API_SECRET")
    assert not hasattr(settings, "EXCHANGE_SECRET")
    assert not hasattr(settings, "PRIVATE_KEY")
