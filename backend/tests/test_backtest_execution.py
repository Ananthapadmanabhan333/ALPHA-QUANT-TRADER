from datetime import datetime, timezone, timedelta
import pytest
import pandas as pd

from app.backtest.accounting import PortfolioLedger
from app.backtest.constants import OrderSide, OrderType
from app.backtest.cost_model import CostModel
from app.backtest.engine import BacktestEngine
from app.backtest.execution import Order, SimulatedExecutionEngine
from app.quant.strategy.trend_following import TrendFollowingStrategy
from tests.test_quant_strategies import create_synthetic_candles


def test_next_bar_execution_strictly_at_open():
    """
    CRITICAL LOOK-AHEAD PREVENTION TEST:
    Verify that an order queued at bar t executes strictly at bar t+1 OPEN price.
    """
    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)

    cost_model = CostModel(taker_fee_bps=0.0, slippage_bps=0.0, assumed_spread_bps=0.0)
    exec_engine = SimulatedExecutionEngine(cost_model=cost_model)
    ledger = PortfolioLedger(initial_cash=10000.0)

    # Submit order at bar 0
    exec_engine.submit_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        timestamp=t0,
    )
    assert len(exec_engine.pending_orders) == 1

    # Bar 1 arrives: Open=50000, High=50500, Low=49500, Close=50200
    bar_1 = {
        "open_time": t1,
        "open": 50000.0,
        "high": 50500.0,
        "low": 49500.0,
        "close": 50200.0,
        "volume": 100.0,
    }

    trades = exec_engine.process_next_bar_executions(bar_1, ledger)
    assert len(trades) == 1
    trade = trades[0]

    # Fill MUST be at Open (50000.0), NOT High, Low, or Close!
    assert trade.fill_price == 50000.0
    assert trade.quantity == 0.1
    assert trade.gross_notional == 5000.0
    assert trade.timestamp == t1
    assert len(exec_engine.pending_orders) == 0


def test_adverse_slippage_and_fee_deductions():
    """
    Verify that:
    - Buys slip upwards: Fill = Ref * (1 + slip + spread/2)
    - Sells slip downwards: Fill = Ref * (1 - slip - spread/2)
    - Fees are calculated on gross notional
    - Net P&L = Gross P&L - Fees - Slippage
    """
    cost_model = CostModel(
        maker_fee_bps=5.0,
        taker_fee_bps=10.0,      # 0.10%
        slippage_bps=5.0,        # 0.05%
        assumed_spread_bps=2.0,  # 0.02% total spread -> 0.01% half-spread
    )
    # Total buy penalty = 0.05% + 0.01% = 0.06% = 0.0006
    ref_price = 10000.0
    fill_buy, slip_buy = cost_model.calculate_fill_price(ref_price, OrderSide.BUY)
    expected_buy = ref_price * (1.0 + 0.0006)
    assert pytest.approx(fill_buy) == expected_buy
    assert pytest.approx(slip_buy) == expected_buy - ref_price

    fill_sell, slip_sell = cost_model.calculate_fill_price(ref_price, OrderSide.SELL)
    expected_sell = ref_price * (1.0 - 0.0006)
    assert pytest.approx(fill_sell) == expected_sell
    assert pytest.approx(slip_sell) == ref_price - expected_sell

    # Fee on $50,000 notional at 10 bps
    fee = cost_model.calculate_fee(50000.0, is_maker=False)
    assert pytest.approx(fee) == 50.0  # $50,000 * 0.0010 = $50.0


def test_portfolio_ledger_accounting_invariants():
    """
    Verify fundamental financial invariants:
    - Total Equity = Cash + Position Value
    - Realized Net P&L = Realized Gross P&L - Fees - Slippage
    """
    ledger = PortfolioLedger(initial_cash=10000.0)
    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

    # Buy 0.5 BTC at $10,000 with $5 fee and $2.50 slippage
    ledger.record_buy(
        trade_id="t1",
        order_id="o1",
        timestamp=t0,
        symbol="BTCUSDT",
        fill_price=10000.0,
        quantity=0.5,
        fee=5.0,
        slippage_cost=5.0,  # per unit -> $2.50 total
    )

    # Cash should be 10000 - 5000 - 5 = 4995.0
    assert pytest.approx(ledger.cash) == 4995.0
    pos = ledger.get_position("BTCUSDT")
    assert pos.quantity == 0.5
    assert pytest.approx(pos.avg_entry_price) == 10000.0

    # Snapshot when market is at $11,000
    snap1 = ledger.record_bar_snapshot(t0, {"BTCUSDT": 11000.0})
    # Position value = 0.5 * 11000 = 5500.0
    # Total equity = 4995.0 + 5500.0 = 10495.0
    assert pytest.approx(snap1.positions_value) == 5500.0
    assert pytest.approx(snap1.total_equity) == 10495.0
    assert pytest.approx(snap1.cash + snap1.positions_value) == snap1.total_equity

    # Sell 0.5 BTC at $11,000 with $5.50 fee
    t1 = t0 + timedelta(minutes=1)
    ledger.record_sell(
        trade_id="t2",
        order_id="o2",
        timestamp=t1,
        symbol="BTCUSDT",
        fill_price=11000.0,
        quantity=0.5,
        fee=5.50,
        slippage_cost=5.0,
    )

    # Cash should be 4995.0 + (5500 - 5.50) = 10489.50
    assert pytest.approx(ledger.cash) == 10489.50
    assert ledger.get_position("BTCUSDT").quantity == 0.0

    snap2 = ledger.record_bar_snapshot(t1, {"BTCUSDT": 11000.0})
    assert pytest.approx(snap2.total_equity) == 10489.50
    # Net profit: 10489.50 - 10000.0 = $489.50
    # Gross profit: (11000 - 10000) * 0.5 = $500.00
    # Total fees: 5.0 + 5.50 = 10.50
    # Total slippage: 2.50 + 2.50 = 5.00
    assert pytest.approx(snap2.gross_pnl) == 500.00
    assert pytest.approx(snap2.net_pnl) == 489.50


def test_liquidity_constraint_enforcement():
    """
    Max volume participation test:
    Order for 20 BTC against bar with only 100 BTC volume (10% max participation = 10 BTC max fill)
    must fill partially at 10 BTC.
    """
    cost_model = CostModel(max_volume_pct=10.0, taker_fee_bps=0.0, slippage_bps=0.0, assumed_spread_bps=0.0)
    exec_engine = SimulatedExecutionEngine(cost_model=cost_model)
    ledger = PortfolioLedger(initial_cash=500000.0)

    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    order = exec_engine.submit_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=20.0,
        timestamp=t0,
    )

    bar = {
        "open_time": t0 + timedelta(minutes=1),
        "open": 10000.0,
        "high": 10100.0,
        "low": 9900.0,
        "close": 10050.0,
        "volume": 100.0,  # 10% max is 10.0 BTC
    }

    trades = exec_engine.process_next_bar_executions(bar, ledger)
    assert len(trades) == 1
    # Only 10 BTC filled due to volume constraint
    assert pytest.approx(trades[0].quantity) == 10.0
    assert order.status.value == "partially_filled"
    # Remaining 10 stays pending
    assert len(exec_engine.pending_orders) == 1
    assert pytest.approx(exec_engine.pending_orders[0].requested_qty) == 10.0


def test_limit_order_execution_semantics():
    cost_model = CostModel(taker_fee_bps=0.0, slippage_bps=0.0, assumed_spread_bps=0.0)
    exec_engine = SimulatedExecutionEngine(cost_model=cost_model)
    ledger = PortfolioLedger(initial_cash=50000.0)

    t0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    # Buy Limit at $9,500
    exec_engine.submit_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        limit_price=9500.0,
        timestamp=t0,
    )

    # Bar 1: Low is 9600 -> Does NOT touch limit price -> No fill
    bar_high = {
        "open_time": t0 + timedelta(minutes=1),
        "open": 9800.0,
        "high": 10000.0,
        "low": 9600.0,
        "close": 9700.0,
        "volume": 100.0,
    }
    trades1 = exec_engine.process_next_bar_executions(bar_high, ledger)
    assert len(trades1) == 0
    assert len(exec_engine.pending_orders) == 1

    # Bar 2: Low reaches 9400 -> Crosses limit -> Fills at limit price
    bar_low = {
        "open_time": t0 + timedelta(minutes=2),
        "open": 9600.0,
        "high": 9700.0,
        "low": 9400.0,
        "close": 9450.0,
        "volume": 100.0,
    }
    trades2 = exec_engine.process_next_bar_executions(bar_low, ledger)
    assert len(trades2) == 1
    assert trades2[0].fill_price == 9500.0
