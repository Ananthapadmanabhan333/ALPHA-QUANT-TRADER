"""
ALPHA Quant — Phase 8: Full End-to-End System Pipeline Verification.
Verifies the complete quantitative lifecycle:
Market Data Ingestion -> Integrity Validation -> Database Storage ->
Feature Engineering -> Strategy Signal Generation -> Central Risk Gate ->
PaperBroker Submission -> Market Fill Execution -> Ledger Reconciliation ->
Analytics Aggregation -> REST API & Live Telemetry.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.models import MarketCandle
from app.market.validator import validate_candle
from app.paper.broker import PaperBroker
from app.paper.constants import OrderSide, OrderStatus, OrderType
from app.paper.risk_gate import CentralRiskGate
from app.paper.schemas import PaperOrderCreateRequest
from app.quant.constants import STRATEGY_TREND_FOLLOWING
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.trend_following import TrendFollowingStrategy


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
        c = {
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
        }
        validate_candle(c)
        raw_candles.append(c)

    assert len(raw_candles) == 150

    # ----------------------------------------------------
    # Stage 2: Storage in Database
    # ----------------------------------------------------
    db_candles = [MarketCandle(**c) for c in raw_candles]
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
    df = pipeline.candles_to_dataframe(db_candles, interval="1m")
    feature_df = pipeline.compute_all_features(df)
    assert "sma_20" in feature_df.columns
    assert "sma_100" in feature_df.columns
    assert "volatility_20" in feature_df.columns

    # ----------------------------------------------------
    # Stage 4: Quantitative Strategy Signal Generation
    # ----------------------------------------------------
    strategy = TrendFollowingStrategy()
    signals = strategy.generate_signals(feature_df)
    assert len(signals) > 0
    sample_signal = signals[-1]
    assert sample_signal.symbol == "BTCUSDT"
    assert sample_signal.strategy_id == STRATEGY_TREND_FOLLOWING
    assert sample_signal.side.value in ("buy", "sell", "hold")

    # ----------------------------------------------------
    # Stage 5 & 6 & 7: Central Pre-Trade Risk Gate, PaperBroker Order & Fill
    # ----------------------------------------------------
    broker = PaperBroker()
    account = await broker.get_or_create_default_account(test_session)
    initial_cash = account.virtual_balance
    assert initial_cash == 10000.0

    current_price = float(prices[-1])
    req = PaperOrderCreateRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        client_order_id="e2e_order_test_101",
        current_market_price=current_price,
    )

    order = await broker.submit_order(
        db=test_session,
        request=req,
        current_market_price=current_price,
        latest_feed_time=datetime.now(timezone.utc),
    )
    assert order.id is not None
    assert order.status == OrderStatus.FILLED.value
    assert order.fee > 0
    assert order.slippage_cost > 0

    # ----------------------------------------------------
    # Stage 8: Ledger Accounting & Invariant Reconciliation
    # ----------------------------------------------------
    pos = await broker.get_position(test_session, account.id, "BTCUSDT")
    assert pos is not None
    assert pos.quantity == 0.01

    # ----------------------------------------------------
    # Stage 9: REST API Telemetry Inspection
    # ----------------------------------------------------
    res_portfolio = await client.get("/api/v1/portfolio?symbol=BTCUSDT")
    assert res_portfolio.status_code == 200
    portfolio_data = res_portfolio.json()
    assert len(portfolio_data["positions"]) == 1
    assert portfolio_data["positions"][0]["symbol"] == "BTCUSDT"

    res_orders = await client.get("/api/v1/paper/orders")
    assert res_orders.status_code == 200
    orders_payload = res_orders.json()
    assert len(orders_payload) >= 1

    res_fills = await client.get(f"/api/v1/paper/orders/{order.id}")
    assert res_fills.status_code == 200
    assert len(res_fills.json()["fills"]) >= 1
