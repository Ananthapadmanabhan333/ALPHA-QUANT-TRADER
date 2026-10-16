"""
API tests for ALPHA Quant Phase 5 Paper Execution & Risk REST endpoints:
- GET /api/v1/paper/account
- POST /api/v1/paper/orders
- GET /api/v1/paper/orders
- GET /api/v1/paper/orders/{order_id}
- DELETE /api/v1/paper/orders/{order_id}
- GET /api/v1/paper/risk/status
- POST /api/v1/paper/risk/emergency-stop
- POST /api/v1/paper/risk/resume
- POST /api/v1/paper/match-market
"""

from datetime import datetime, timezone
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.service import MarketDataService


@pytest.mark.asyncio
async def test_paper_api_account_and_risk_lifecycle(client: AsyncClient, test_session: AsyncSession):
    # 1. Seed fresh market candle so feed is healthy
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

    # 2. GET /api/v1/paper/account
    acc_res = await client.get("/api/v1/paper/account?symbol=BTCUSDT")
    assert acc_res.status_code == 200
    acc_data = acc_res.json()
    assert acc_data["virtual_balance"] == 10000.0
    assert acc_data["total_equity"] == 10000.0
    assert len(acc_data["positions"]) == 0

    # 3. GET /api/v1/paper/risk/status
    risk_res = await client.get("/api/v1/paper/risk/status?symbol=BTCUSDT")
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["emergency_stop"] is False
    assert risk_data["is_trading_allowed"] is True

    # 4. POST /api/v1/paper/orders (BUY Market order within 10% concentration limit)
    # 0.01 BTC @ 50050 = $500.50 (5% of $10,000 equity < 10% limit)
    buy_res = await client.post(
        "/api/v1/paper/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.01,
            "current_market_price": 50050.0,
        },
    )
    assert buy_res.status_code == 201
    buy_data = buy_res.json()
    assert buy_data["status"] == "filled"
    assert buy_data["filled_quantity"] == 0.01
    order_id = buy_data["id"]

    # 5. GET /api/v1/paper/orders/{order_id}
    detail_res = await client.get(f"/api/v1/paper/orders/{order_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["order"]["id"] == order_id
    assert len(detail_data["fills"]) == 1

    # 6. GET /api/v1/paper/positions
    pos_res = await client.get("/api/v1/paper/positions?symbol=BTCUSDT")
    assert pos_res.status_code == 200
    positions = pos_res.json()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTCUSDT"
    assert positions[0]["quantity"] == 0.01

    # 7. POST /api/v1/paper/risk/emergency-stop
    stop_res = await client.post(
        "/api/v1/paper/risk/emergency-stop",
        json={"reason": "Manual operator drill"},
    )
    assert stop_res.status_code == 200
    stop_data = stop_res.json()
    assert stop_data["emergency_stop"] is True
    assert stop_data["is_trading_allowed"] is False

    # 8. Attempting new order during emergency stop must fail with 400
    halt_order_res = await client.post(
        "/api/v1/paper/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.01,
            "current_market_price": 50050.0,
        },
    )
    assert halt_order_res.status_code == 400
    assert "Emergency Stop active" in halt_order_res.text

    # 9. POST /api/v1/paper/risk/resume
    resume_res = await client.post(
        "/api/v1/paper/risk/resume",
        json={"confirmation": "CONFIRM_RESUME", "reset_consecutive_losses": True},
    )
    assert resume_res.status_code == 200
    resume_data = resume_res.json()
    assert resume_data["emergency_stop"] is False

    # 10. POST /api/v1/paper/orders (Limit Order)
    limit_res = await client.post(
        "/api/v1/paper/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "limit",
            "quantity": 0.01,
            "price": 45000.0,
        },
    )
    assert limit_res.status_code == 201
    limit_data = limit_res.json()
    assert limit_data["status"] == "open"
    limit_order_id = limit_data["id"]

    # 11. Match market price
    match_res = await client.post(
        "/api/v1/paper/match-market",
        json={
            "symbol": "BTCUSDT",
            "price": 44500.0,
            "high": 46000.0,
            "low": 44000.0,
        },
    )
    assert match_res.status_code == 200
    matched_fills = match_res.json()
    assert len(matched_fills) >= 1
    assert matched_fills[0]["order_id"] == limit_order_id


@pytest.mark.asyncio
async def test_paper_api_live_trading_rejection(client: AsyncClient):
    """
    Security Invariant Test: Any attempt to pass is_live=True is rejected.
    """
    response = await client.post(
        "/api/v1/paper/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.01,
            "is_live": True,
        },
    )
    assert response.status_code == 422 or response.status_code == 400
    assert "Live trading is strictly prohibited" in response.text
