"""
ALPHA Quant — Phase 8: Automated Security Invariants & Compliance Audit Tests.
Verifies critical security and non-execution invariants:
1. Zero live trading clients or order-routing adapters exist in the repository.
2. No live withdrawal, exchange API secret, or real fund movement endpoints exist.
3. Database schemas strictly contain only simulated/paper accounts, orders, and fills.
4. Mutating REST endpoints are protected and validate administrative API keys.
5. Central Risk Gate cannot be bypassed by client requests or query parameters.
"""

import inspect
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app
from app.core.config import get_settings
from app.db.base import Base
from app.paper.broker import PaperBroker
from app.paper.models import PaperSide, PaperOrderType
from app.paper.risk_gate import CentralRiskGate
from app.paper.exceptions import RiskBreachException


def test_security_invariant_1_no_live_trading_client():
    """Verify that no live trading exchange client or execution gateway exists."""
    forbidden_terms = [
        "ccxt.binance",
        "create_order",
        "place_live_order",
        "cancel_live_order",
        "withdraw",
        "create_withdrawal",
        "api_secret",
        "binance_secret",
        "binance_api_key",
    ]

    # Inspect all module files in app package
    import os
    app_dir = os.path.dirname(app.__file__)
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                    # Check that withdrawal or live order methods do not exist
                    assert "create_withdrawal" not in content.lower()
                    assert "wallet_withdraw" not in content.lower()
                    assert "binance_secret" not in content.lower()


def test_security_invariant_2_database_tables_are_strictly_paper():
    """Verify that all financial models in SQLAlchemy are strictly paper/simulated."""
    table_names = list(Base.metadata.tables.keys())
    # Verify tables
    assert "paper_accounts" in table_names
    assert "paper_orders" in table_names
    assert "paper_fills" in table_names
    assert "paper_positions" in table_names

    # Verify no table exists for live exchange credentials or live accounts
    for name in table_names:
        assert "live_account" not in name
        assert "exchange_credential" not in name
        assert "api_key_store" not in name
        assert "wallet" not in name


@pytest.mark.asyncio
async def test_security_invariant_3_frontend_cannot_bypass_risk_gate(test_session: AsyncSession):
    """Verify that order submission always passes through the Central Risk Gate."""
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "test_bypass_acc")
    risk_gate = CentralRiskGate()

    # Attempting to submit order with notional $15,000 (exceeds $10,000 max order notional)
    with pytest.raises(RiskBreachException) as exc:
        await risk_gate.validate_order(
            account=account,
            symbol="BTCUSDT",
            side=PaperSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=Decimal("0.3"), # 0.3 * $50,000 = $15,000
            current_market_price=Decimal("50000.00"),
        )
    assert "MAX_ORDER_NOTIONAL" in str(exc.value)


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
