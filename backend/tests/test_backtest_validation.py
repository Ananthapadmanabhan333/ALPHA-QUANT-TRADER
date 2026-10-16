from datetime import datetime, timezone, timedelta
import pytest
import pandas as pd

from app.backtest.cost_model import CostModel
from app.backtest.engine import BacktestEngine
from app.backtest.validation import (
    classify_market_regimes,
    generate_walk_forward_windows,
    split_chronological,
)
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.trend_following import TrendFollowingStrategy
from tests.test_quant_strategies import create_synthetic_candles


def test_chronological_splits_and_untouched_holdout():
    records = create_synthetic_candles(100, lambda i: 100.0 + i)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)

    partitions = split_chronological(df, train_ratio=0.6, val_ratio=0.2, holdout_ratio=0.2)

    # 100 bars -> 60 train, 20 val, 20 holdout
    assert len(partitions.train) == 60
    assert len(partitions.validation) == 20
    assert len(partitions.holdout) == 20

    # Verify strictly chronological ordering
    train_max_time = partitions.train["open_time"].max()
    val_min_time = partitions.validation["open_time"].min()
    val_max_time = partitions.validation["open_time"].max()
    holdout_min_time = partitions.holdout["open_time"].min()

    assert train_max_time < val_min_time
    assert val_max_time < holdout_min_time


def test_walk_forward_windows_generator():
    records = create_synthetic_candles(160, lambda i: 100.0 + i)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)

    windows = list(generate_walk_forward_windows(df, train_bars=100, test_bars=30, step_bars=30))
    # 0: train 0..100, test 100..130
    # 1: train 30..130, test 130..160
    assert len(windows) == 2

    w0_idx, w0_train, w0_test = windows[0]
    assert w0_idx == 0
    assert len(w0_train) == 100
    assert len(w0_test) == 30
    assert w0_train["open_time"].max() < w0_test["open_time"].min()


def test_market_regime_classification():
    # 50 flat bars, then 30 upward bars (bullish), then 30 downward bars (bearish)
    def price_curve(i):
        if i < 50:
            return 100.0
        elif i < 80:
            return 100.0 + (i - 50) * 1.5  # Strong rally
        else:
            return 145.0 - (i - 80) * 2.0  # Sharp crash

    records = create_synthetic_candles(110, price_curve)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)

    regimes = classify_market_regimes(df, window=10)
    assert len(regimes) == 110
    # Initial flat period has choppy / baseline regimes
    assert regimes.iloc[10] in ("choppy", "high_volatility")
    # Rally bars should register bullish
    assert "bullish" in regimes.values
    # Crash bars should register bearish or high_volatility
    assert "bearish" in regimes.values or "high_volatility" in regimes.values


def test_end_to_end_backtest_determinism():
    """
    Verify that executing BacktestEngine twice on the exact same dataset
    produces identical final equity, trade count, Sharpe, and metrics.
    """
    records = create_synthetic_candles(150, lambda i: 100.0 if i < 110 else (100.0 + (i - 110) * 1.0 if i <= 130 else 120.0 - (i - 130) * 2.0))
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)

    strat = TrendFollowingStrategy()
    engine = BacktestEngine(
        cost_model=CostModel(taker_fee_bps=10.0, slippage_bps=5.0),
        initial_cash=10000.0,
    )

    res1 = engine.run(strat, df, run_stress_tests=False)
    res2 = engine.run(strat, df, run_stress_tests=False)

    assert res1.dataset_fingerprint == res2.dataset_fingerprint
    assert res1.performance.final_equity == res2.performance.final_equity
    assert res1.performance.net_return_pct == res2.performance.net_return_pct
    assert res1.performance.sharpe_ratio == res2.performance.sharpe_ratio
    assert res1.performance.total_trades == res2.performance.total_trades
    assert len(res1.trades) == len(res2.trades)
