"""
Unit tests for ALPHA Quant Phase 5 PaperBroker:
- Insufficient balance & inventory rejections
- Idempotent order submissions
- Market order fill semantics (fees, adverse slippage, weighted average cost)
- Partial fill simulation
- Limit order lifecycle & match_open_orders
- Order cancellation
- Portfolio reconciliation & restart recovery
"""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperOrder
from app.paper.broker import PaperBroker
from app.paper.constants import OrderSide, OrderStatus, OrderType
from app.paper.exceptions import (
    InsufficientBalanceException,
    OrderNotFoundException,
)
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest


@pytest.mark.asyncio
async def test_paper_broker_insufficient_cash(test_session: AsyncSession):
    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    risk_state = await broker.get_account_risk_state(test_session, account.id)
    # Relax risk gate thresholds to specifically test broker cash balance sufficiency check
    risk_state.max_order_notional = 50000.0
    risk_state.max_position_pct = 5.0
    risk_state.max_portfolio_exposure_pct = 5.0
    await test_session.commit()

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.5,  # 0.5 BTC @ 50,000 = $25,000 > $10,000 virtual balance
        current_market_price=50000.0,
    )

    with pytest.raises(InsufficientBalanceException) as exc_info:
        await broker.submit_order(
            db=test_session,
            request=req,
            current_market_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )

    assert "Insufficient virtual cash balance" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paper_broker_insufficient_inventory_for_sell(test_session: AsyncSession):
    broker = PaperBroker()
    await broker.get_or_create_default_account(test_session)

    # Attempt to sell BTC when account holds 0 BTC
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.005,
        current_market_price=50000.0,
    )

    with pytest.raises(InsufficientBalanceException) as exc_info:
        await broker.submit_order(
            db=test_session,
            request=req,
            current_market_price=50000.0,
            latest_feed_time=datetime.now(timezone.utc),
        )

    assert "Insufficient spot inventory" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paper_broker_idempotency_duplicate_client_order_id(test_session: AsyncSession):
    broker = PaperBroker()
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="idemp-key-12345",
        current_market_price=50000.0,
    )

    now = datetime.now(timezone.utc)
    order1 = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    assert order1.status == OrderStatus.FILLED.value
    order1_id = order1.id

    # Resubmit with identical client_order_id
    order2 = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    assert order2.id == order1_id
    assert order2.status == OrderStatus.FILLED.value


@pytest.mark.asyncio
async def test_paper_broker_market_buy_and_sell_accounting(test_session: AsyncSession):
    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    initial_cash = account.virtual_balance  # 10,000.0

    now = datetime.now(timezone.utc)

    # 1. Buy 0.01 BTC at mark price $50,000
    buy_req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="order-buy-001",
        current_market_price=50000.0,
    )
    buy_order = await broker.submit_order(test_session, buy_req, 50000.0, latest_feed_time=now)
    assert buy_order.status == OrderStatus.FILLED.value
    # Adverse slippage for BUY adds 5 bps (0.05% of 50000 = +25 -> 50025)
    assert buy_order.avg_fill_price == pytest.approx(50025.0)
    assert buy_order.fee > 0

    # Verify position created
    pos = await broker.get_position(test_session, account.id, "BTCUSDT")
    assert pos is not None
    assert pos.quantity == pytest.approx(0.01)
    assert pos.avg_entry_price == pytest.approx(50025.0)
    assert account.virtual_balance < initial_cash

    # 2. Sell 0.01 BTC at mark price $52,000 (profitable trade)
    sell_req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="order-sell-001",
        current_market_price=52000.0,
    )
    sell_order = await broker.submit_order(test_session, sell_req, 52000.0, latest_feed_time=now)
    assert sell_order.status == OrderStatus.FILLED.value
    # Adverse slippage for SELL subtracts 5 bps (0.05% of 52000 = -26 -> 51974)
    assert sell_order.avg_fill_price == pytest.approx(51974.0)

    # Verify position closed
    await test_session.refresh(pos)
    assert pos.quantity == pytest.approx(0.0)
    assert pos.realized_pnl > 0  # Profitable trade after fees and slippage

    # Consecutive losses should be 0
    risk_state = await broker.get_account_risk_state(test_session, account.id)
    assert risk_state.consecutive_losses == 0


@pytest.mark.asyncio
async def test_paper_broker_partial_fill_liquidity_cap(test_session: AsyncSession):
    broker = PaperBroker()
    now = datetime.now(timezone.utc)

    # Bar volume is 0.05 BTC. Max participation cap (10%) is 0.005 BTC.
    # Order quantity is 0.01 BTC.
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="order-part-001",
        current_market_price=50000.0,
    )
    order = await broker.submit_order(
        db=test_session,
        request=req,
        current_market_price=50000.0,
        latest_feed_time=now,
        bar_volume=0.05,
    )
    assert order.status == OrderStatus.PARTIALLY_FILLED.value
    assert order.filled_quantity == pytest.approx(0.005)


@pytest.mark.asyncio
async def test_paper_broker_limit_order_lifecycle(test_session: AsyncSession):
    broker = PaperBroker()
    now = datetime.now(timezone.utc)

    # 1. Place limit BUY below market price ($48,000 when market is $50,000)
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        price=48000.0,
        client_order_id="limit-buy-001",
    )
    order = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    assert order.status == OrderStatus.OPEN.value
    assert order.filled_quantity == 0.0

    # 2. Market price does not touch limit ($49,000 - $51,000)
    fills = await broker.match_open_orders(
        db=test_session,
        symbol="BTCUSDT",
        high_price=51000.0,
        low_price=49000.0,
        close_price=50000.0,
    )
    assert len(fills) == 0

    # 3. Market price dips to $47,500 (touches $48,000 limit)
    fills = await broker.match_open_orders(
        db=test_session,
        symbol="BTCUSDT",
        high_price=49500.0,
        low_price=47500.0,
        close_price=48000.0,
    )
    assert len(fills) == 1
    assert fills[0].fill_price == 48000.0
    await test_session.refresh(order)
    assert order.status == OrderStatus.FILLED.value


@pytest.mark.asyncio
async def test_paper_broker_cancel_order(test_session: AsyncSession):
    broker = PaperBroker()
    now = datetime.now(timezone.utc)

    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.01,
        price=45000.0,
        client_order_id="limit-cancel-001",
    )
    order = await broker.submit_order(test_session, req, 50000.0, latest_feed_time=now)
    assert order.status == OrderStatus.OPEN.value

    # Cancel order
    cancelled = await broker.cancel_order(test_session, order.id)
    assert cancelled.status == OrderStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_paper_broker_reconciliation_and_restart(test_session: AsyncSession):
    broker = PaperBroker()
    rec = await broker.reconcile_portfolio(test_session, current_market_price=50000.0, symbol="BTCUSDT")
    assert rec["virtual_balance"] == 10000.0
    assert rec["total_equity"] == 10000.0
    assert rec["is_emergency_stop"] is False
