from datetime import datetime, timezone, timedelta
import pytest
import numpy as np
import pandas as pd

from app.quant.constants import SignalSide
from app.quant.exceptions import InsufficientDataException
from app.quant.experiments.tracker import (
    ExperimentService,
    compute_dataset_fingerprint,
)
from app.quant.features.pipeline import FeaturePipeline
from app.quant.strategy.mean_reversion import MeanReversionStrategy
from app.quant.strategy.momentum import MomentumStrategy
from app.quant.strategy.trend_following import TrendFollowingStrategy


def create_synthetic_candles(n: int, price_func, start_time=None):
    if start_time is None:
        start_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    records = []
    for i in range(n):
        price = price_func(i)
        records.append({
            "open_time": start_time + timedelta(minutes=i),
            "close_time": start_time + timedelta(minutes=i, seconds=59),
            "open": float(price),
            "high": float(price * 1.002),
            "low": float(price * 0.998),
            "close": float(price),
            "volume": 100.0,
            "is_closed": True,
            "symbol": "BTCUSDT",
            "interval": "1m",
        })
    return records


def test_trend_following_signals_deterministic():
    """
    Construct price series:
    - 0 to 110: flat at 100.0 (warm-up)
    - 110 to 130: strong upward trend (fast SMA > slow SMA, calm vol) -> BUY
    - 131 to 150: sharp decline (fast SMA crosses below slow SMA) -> SELL
    """
    def price_curve(i):
        if i < 110:
            return 100.0
        elif i <= 130:
            return 100.0 + (i - 110) * 1.0  # Rises to 120
        else:
            return 120.0 - (i - 130) * 2.0  # Collapses to 80

    records = create_synthetic_candles(150, price_curve)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)
    features_df = pipeline.compute_all_features(df)

    strat = TrendFollowingStrategy()
    signals = strat.generate_signals(features_df)

    assert len(signals) == 150
    # Warmup period bars must be HOLD
    for s in signals[:100]:
        assert s.side == SignalSide.HOLD
        assert "Warm-up" in s.reason

    # During uptrend (entry happens at bar 111), fast MA > slow MA -> BUY
    uptrend_signals = [s for s in signals[100:130] if s.side == SignalSide.BUY]
    assert len(uptrend_signals) > 0
    assert uptrend_signals[0].signal_score > 0

    # During decline (at bar 149), fast MA drops below slow MA -> SELL
    downtrend_signals = [s for s in signals[135:] if s.side == SignalSide.SELL]
    assert len(downtrend_signals) > 0
    assert downtrend_signals[0].side == SignalSide.SELL


def test_mean_reversion_signals_deterministic():
    """
    Construct price series:
    - 0 to 105: steady oscillations around 100.0 (warmup completed at 100)
    - 105 to 115: oversold plunge to 90.0 (z-score <= -2.0) -> BUY
    - 116 to 130: bounce back to 102.0 (z-score >= 0.0) -> SELL
    """
    def price_curve(i):
        if i < 105:
            return 100.0 + (1.0 if i % 2 == 0 else -1.0)
        elif i < 116:
            return 90.0  # Oversold plunge
        else:
            return 102.0  # Reversion bounce

    records = create_synthetic_candles(130, price_curve)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)
    features_df = pipeline.compute_all_features(df)

    strat = MeanReversionStrategy()
    signals = strat.generate_signals(features_df)

    assert len(signals) == 130
    # Look for BUY signal during extreme drop (bars 105-115)
    buy_signals = [s for s in signals[105:116] if s.side == SignalSide.BUY]
    assert len(buy_signals) > 0
    assert buy_signals[0].signal_score > 0

    # Look for SELL exit on mean bounce (bars 116-130)
    sell_signals = [s for s in signals[116:] if s.side == SignalSide.SELL]
    assert len(sell_signals) > 0
    assert "reverted to target" in sell_signals[0].reason or "Explicit" in sell_signals[0].reason


def test_momentum_signals_deterministic():
    """
    Construct price series:
    - 0 to 70: flat (warm-up)
    - 71 to 85: steady growth (momentum > hurdle) -> BUY at 71
    - 86 to 100: momentum collapse/reversal -> SELL at 90
    """
    def price_curve(i):
        if i < 70:
            return 100.0
        elif i <= 85:
            return 100.0 + (i - 70) * 0.5  # Growth
        else:
            return 107.5 - (i - 85) * 1.0  # Decline

    records = create_synthetic_candles(100, price_curve)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)
    features_df = pipeline.compute_all_features(df)

    strat = MomentumStrategy()
    signals = strat.generate_signals(features_df)

    assert len(signals) == 100
    buys = [s for s in signals[70:85] if s.side == SignalSide.BUY]
    assert len(buys) > 0

    sells = [s for s in signals[85:] if s.side == SignalSide.SELL]
    assert len(sells) > 0
    assert "turned non-positive" in sells[0].reason or "faded" in sells[0].reason


def test_experiment_fingerprint_and_reproducibility():
    """
    Verifies that running the same strategy on the same data slice produces
    the EXACT same dataset fingerprint, config ID, and signals.
    """
    records = create_synthetic_candles(120, lambda i: 100.0 + (i * 0.2))
    pipeline = FeaturePipeline()
    df1 = pipeline.candles_to_dataframe(records)
    df2 = pipeline.candles_to_dataframe(records)

    fp1 = compute_dataset_fingerprint(df1)
    fp2 = compute_dataset_fingerprint(df2)
    assert fp1 == fp2

    exp_service = ExperimentService(pipeline)
    strat1 = exp_service.create_strategy_instance("trend_following")
    strat2 = exp_service.create_strategy_instance("trend_following")
    assert strat1.config_id == strat2.config_id

    _, sigs1, _, _ = exp_service.run_strategy_on_dataframe(strat1, df1)
    _, sigs2, _, _ = exp_service.run_strategy_on_dataframe(strat2, df2)

    assert len(sigs1) == len(sigs2)
    for s1, s2 in zip(sigs1, sigs2):
        assert s1.decision_timestamp == s2.decision_timestamp
        assert s1.side == s2.side
        assert s1.signal_score == s2.signal_score
        assert s1.reference_price == s2.reference_price


def test_strategy_lookahead_bias_prevention():
    """
    Modifying bar t+1 does not change the decision or signal at bar t.
    """
    records_orig = create_synthetic_candles(120, lambda i: 100.0 + (i * 0.1))
    pipeline = FeaturePipeline()
    df_orig = pipeline.candles_to_dataframe(records_orig)
    feats_orig = pipeline.compute_all_features(df_orig)

    strat = TrendFollowingStrategy()
    signals_orig = strat.generate_signals(feats_orig)
    sig_at_100_orig = signals_orig[100]

    # Mutate everything after index 100
    records_mut = [dict(r) for r in records_orig]
    for i in range(101, 120):
        records_mut[i]["close"] = 999999.0
        records_mut[i]["high"] = 999999.0
        records_mut[i]["open"] = 999999.0

    df_mut = pipeline.candles_to_dataframe(records_mut)
    feats_mut = pipeline.compute_all_features(df_mut)
    signals_mut = strat.generate_signals(feats_mut)
    sig_at_100_mut = signals_mut[100]

    assert sig_at_100_orig.side == sig_at_100_mut.side
    assert sig_at_100_orig.signal_score == sig_at_100_mut.signal_score
    assert sig_at_100_orig.reason == sig_at_100_mut.reason
    assert sig_at_100_orig.reference_price == sig_at_100_mut.reference_price


def test_strategy_insufficient_data_rejection():
    records = create_synthetic_candles(10, lambda i: 100.0)
    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)
    feats = pipeline.compute_all_features(df)
    strat = TrendFollowingStrategy()
    with pytest.raises(InsufficientDataException):
        strat.generate_signals(feats)
