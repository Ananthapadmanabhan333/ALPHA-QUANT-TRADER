"""
ALPHA Quant — Phase 8: Full End-to-End System Pipeline Verification.
Verifies the complete quantitative lifecycle:
Market Data Ingestion → Integrity Validation → TimescaleDB Storage →
Feature Engineering → Strategy Signal Generation → Central Risk Gate →
PaperBroker Submission → Market Fill Execution → Ledger Reconciliation →
Analytics Aggregation → REST API & Live Telemetry.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.models import MarketCandle
from app.market.validator import MarketDataValidator
from app.paper.broker import PaperBroker
from app.paper.models import PaperOrderType, PaperSide, PaperOrderStatus
from app.paper.risk_gate import CentralRiskGate
from app.quant.constants import STRATEGY_TREND_FOLLOWING
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategies.trend_following import TrendFollowingStrategy


@pytest.mark.asyncio
async def test_complete_e2e_pipeline(test_session: AsyncSession, client: AsyncClient):
    """
    Executes and audits the entire 9-stage quantitative pipeline from market candles
    to fills, accounting invariants, and API inspection.
    """
    # ----------------------------------------------------
    # Stage 1: Market Data Ingestion & Integrity Validation
    # ----------------------------------------------------
    base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    raw_candles = []
    prices = [50000.0 + (i * 10.0 if i < 110 else -i * 5.0) for i in range(150)]

    for idx, price in enumerate(prices):
        open_t = base_time + timedelta(minutes=idx)
        close_t = open_t + timedelta(minutes=1)
        raw_candles.append({
            "symbol": "BTCUSDT",
            "interval": "1m",
            "open_time": open_t,
            "close_time": close_t,
            "open": price - 2.0,
            "high": price + 5.0,
            "low": price - 5.0,
            "close": price,
            "volume": 10.5,
            "quote_volume": price * 10.5,
            "trades_count": 50,
            "is_closed": True,
            "source": "binance_spot",
            "ingested_at": datetime.now(timezone.utc),
        })

    # Validate candles
    valid_candles = [MarketDataValidator.validate_candle(c) for c in raw_candles]
    assert len(valid_candles) == 150

    # ----------------------------------------------------
    # Stage 2: Storage in Database
    # ----------------------------------------------------
    db_candles = [MarketCandle(**c) for c in valid_candles]
    test_session.add_all(db_candles)
    await test_session.commit()

    # Verify query via REST API
    res_candles = await client.get("/api/v1/market/candles?symbol=BTCUSDT&interval=1m&limit=150")
    assert res_candles.status_code == 200
    assert len(res_candles.json()["candles"]) == 150

    # ----------------------------------------------------
    # Stage 3: Feature Pipeline Generation
    # ----------------------------------------------------
    pipeline = FeaturePipeline()
    feature_df = pipeline.compute_features(valid_candles, interval="1m")
    assert "sma_20" in feature_df.columns
    assert "sma_100" in feature_df.columns
    assert "volatility_20" in feature_df.columns

    # ----------------------------------------------------
    # Stage 4: Quantitative Strategy Signal Generation
    # ----------------------------------------------------
    strategy = TrendFollowingStrategy()
    signals = strategy.generate_signals(feature_df)
    assert len(signals) > 0
    # Must have produced at least one typed signal
    sample_signal = signals[-1]
    assert sample_signal.symbol == "BTCUSDT"
    assert sample_signal.strategy_id == STRATEGY_TREND_FOLLOWING
    assert sample_signal.side in ("buy", "sell", "hold")

    # ----------------------------------------------------
    # Stage 5: Central Pre-Trade Risk Gate
    # ----------------------------------------------------
    broker = PaperBroker()
    account = await broker.get_or_create_account(test_session, "e2e_test_account")
    initial_cash = account.virtual_balance
    assert initial_cash == Decimal("10000.00")

    risk_gate = CentralRiskGate()
    # Update feed time to now so freshness check passes
    risk_gate.update_feed_time("BTCUSDT", datetime.now(timezone.utc))

    # Validate proposed simulated order
    order_qty = Decimal("0.01")
    current_price = Decimal(str(prices[-1]))
    passed = await risk_gate.validate_order(
        account=account,
        symbol="BTCUSDT",
        side=PaperSide.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=order_qty,
        current_market_price=current_price,
    )
    assert passed is True

    # ----------------------------------------------------
    # Stage 6: PaperBroker Submission & Order Creation
    # ----------------------------------------------------
    order = await broker.create_order(
        db=test_session,
        account=account,
        symbol="BTCUSDT",
        side=PaperSide.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=order_qty,
        client_order_id="e2e_order_test_101",
    )
    assert order.id is not None
    assert order.status == PaperOrderStatus.OPEN

    # ----------------------------------------------------
    # Stage 7: Market Fill Processing (Fee & Slippage Deductions)
    # ----------------------------------------------------
    fill = await broker.fill_market_order(
        db=test_session,
        account=account,
        order=order,
        next_price=current_price,
    )
    assert fill is not None
    assert order.status == PaperOrderStatus.FILLED
    assert fill.fee > Decimal("0")
    assert fill.slippage_cost > Decimal("0")

    # ----------------------------------------------------
    # Stage 8: Ledger Accounting & Invariant Reconciliation
    # ----------------------------------------------------
    # Invariant: Equity = Cash + Positions Value
    # Cash was debited: notional + fee + slippage
    expected_cash = initial_cash - fill.gross_notional - fill.fee - fill.slippage_cost
    assert abs(account.virtual_balance - expected_cash) < Decimal("0.01")

    # Position inventory created
    pos = await broker.get_position(test_session, account.id, "BTCUSDT")
    assert pos is not None
    assert pos.quantity == order_qty

    # ----------------------------------------------------
    # Stage 9: REST API Telemetry Inspection
    # ----------------------------------------------------
    res_portfolio = await client.get("/api/v1/portfolio?symbol=BTCUSDT")
    assert res_portfolio.status_code == 200
    portfolio_data = res_portfolio.json()
    assert portfolio_data["virtual_balance"] == float(account.virtual_balance)
    assert len(portfolio_data["positions"]) == 1
    assert portfolio_data["positions"][0]["symbol"] == "BTCUSDT"

    # Verify orders API
    res_orders = await client.get("/api/v1/orders")
    assert res_orders.status_code == 200
    assert len(res_orders.json()["items"]) >= 1

    # Verify fills API
    res_fills = await client.get("/api/v1/fills")
    assert res_fills.status_code == 200
    assert len(res_fills.json()["items"]) >= 1
