from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import pytest

from app.quant.exceptions import DataIntegrityException, InsufficientDataException
from app.quant.features.atr import compute_atr, compute_true_range
from app.quant.features.momentum import compute_momentum, compute_multi_period_momentum
from app.quant.features.moving_averages import compute_ema, compute_sma
from app.quant.features.orderbook import compute_order_book_imbalance, compute_spread
from app.quant.features.pipeline import FeaturePipeline
from app.quant.features.returns import compute_log_returns, compute_simple_returns
from app.quant.features.volatility import compute_rolling_volatility
from app.quant.features.volume import (
    compute_volume_ratio,
    compute_volume_sma,
    compute_volume_zscore,
)
from app.quant.features.zscores import compute_rolling_zscore


def test_sma_formula_and_warmup():
    series = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], name="close")
    sma3 = compute_sma(series, window=3)

    # First window - 1 = 2 entries must be NaN
    assert pd.isna(sma3.iloc[0])
    assert pd.isna(sma3.iloc[1])
    # index 2: (10 + 20 + 30) / 3 = 20.0
    assert pytest.approx(sma3.iloc[2]) == 20.0
    # index 3: (20 + 30 + 40) / 3 = 30.0
    assert pytest.approx(sma3.iloc[3]) == 30.0
    # index 4: (30 + 40 + 50) / 3 = 40.0
    assert pytest.approx(sma3.iloc[4]) == 40.0


def test_ema_formula_and_warmup():
    series = pd.Series([10.0, 10.0, 20.0, 30.0], name="close")
    ema3 = compute_ema(series, window=3)

    # First 2 entries masked as NaN
    assert pd.isna(ema3.iloc[0])
    assert pd.isna(ema3.iloc[1])
    # Values at index 2 and index 3 are finite numbers
    assert pd.notna(ema3.iloc[2])
    assert pd.notna(ema3.iloc[3])


def test_simple_and_log_returns():
    series = pd.Series([100.0, 105.0, 110.0], name="close")
    sim_ret = compute_simple_returns(series)
    log_ret = compute_log_returns(series)

    # Bar 0 is NaN (warm-up 1 period)
    assert pd.isna(sim_ret.iloc[0])
    assert pd.isna(log_ret.iloc[0])

    # Bar 1: (105 - 100) / 100 = 0.05
    assert pytest.approx(sim_ret.iloc[1]) == 0.05
    assert pytest.approx(log_ret.iloc[1]) == np.log(105.0 / 100.0)

    # Mathematical identity: exp(log_ret) - 1 == sim_ret
    assert pytest.approx(np.exp(log_ret.iloc[2]) - 1.0) == sim_ret.iloc[2]


def test_rolling_volatility():
    # Constant prices -> zero returns -> zero volatility
    flat = pd.Series([100.0] * 10, name="close")
    vol = compute_rolling_volatility(flat, window=5)
    # Warmup is window + 1 = 6 bars
    assert pd.isna(vol.iloc[4])
    assert pytest.approx(vol.iloc[5], abs=1e-7) == 0.0

    # Variable prices
    prices = pd.Series([100.0, 102.0, 101.0, 105.0, 103.0, 106.0, 108.0], name="close")
    vol = compute_rolling_volatility(prices, window=3)
    assert pd.notna(vol.iloc[4])
    assert vol.iloc[4] > 0.0


def test_rolling_zscore():
    # 5 bars: 10, 20, 30, 40, 50. Mean at bar 4 is 30, std = 15.811
    prices = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], name="close")
    z = compute_rolling_zscore(prices, window=5)
    assert pd.isna(z.iloc[3])
    # Bar 4 is 50 -> above mean -> positive z-score
    assert pd.notna(z.iloc[4])
    assert z.iloc[4] > 1.0


def test_atr_calculation():
    high = pd.Series([10.0, 15.0, 14.0, 20.0])
    low = pd.Series([8.0, 11.0, 10.0, 16.0])
    close = pd.Series([9.0, 12.0, 13.0, 18.0])

    tr = compute_true_range(high, low, close)
    assert tr.iloc[0] == 2.0  # H - L = 10 - 8
    # Bar 1: max(15 - 11 = 4, |15 - 9| = 6, |11 - 9| = 2) = 6.0
    assert tr.iloc[1] == 6.0

    atr2 = compute_atr(high, low, close, window=2)
    assert pd.isna(atr2.iloc[0])
    assert pytest.approx(atr2.iloc[1]) == (2.0 + 6.0) / 2.0


def test_volume_statistics():
    v = pd.Series([100.0, 200.0, 300.0, 400.0], name="volume")
    sma2 = compute_volume_sma(v, window=2)
    ratio2 = compute_volume_ratio(v, window=2)
    z2 = compute_volume_zscore(v, window=2)

    assert pd.isna(sma2.iloc[0])
    assert pytest.approx(sma2.iloc[1]) == 150.0
    assert pytest.approx(ratio2.iloc[1]) == 200.0 / 150.0
    assert pd.notna(z2.iloc[1])


def test_momentum_multi_period():
    prices = pd.Series([100.0, 102.0, 105.0, 110.0], name="close")
    mom1 = compute_momentum(prices, period=1)
    mom3 = compute_momentum(prices, period=3)

    assert pytest.approx(mom1.iloc[1]) == 0.02
    assert pd.isna(mom3.iloc[2])
    # index 3: (110 - 100) / 100 = 0.10
    assert pytest.approx(mom3.iloc[3]) == 0.10

    multi = compute_multi_period_momentum(prices, [1, 3])
    assert "close_momentum_1" in multi
    assert "close_momentum_3" in multi


def test_orderbook_graceful_handling():
    spread = compute_spread(None, None, 5)
    obi = compute_order_book_imbalance(None, None, 5)
    assert len(spread) == 5
    assert spread.isna().all()
    assert len(obi) == 5
    assert obi.isna().all()


def test_feature_pipeline_lookahead_bias_prevention():
    """
    CRITICAL LOOK-AHEAD PREVENTION TEST:
    Modifying future bars (t+1, t+2...) MUST NOT alter feature values at bar t.
    """
    base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    np.random.seed(42)
    n = 120

    records_original = []
    for i in range(n):
        records_original.append({
            "open_time": base_time + timedelta(minutes=i),
            "close_time": base_time + timedelta(minutes=i, seconds=59),
            "open": 50000.0 + float(i),
            "high": 50010.0 + float(i),
            "low": 49990.0 + float(i),
            "close": 50005.0 + float(i),
            "volume": 10.0 + float(i),
            "is_closed": True,
            "symbol": "BTCUSDT",
            "interval": "1m",
        })

    pipeline = FeaturePipeline()
    df_orig = pipeline.candles_to_dataframe(records_original)
    feats_orig = pipeline.compute_all_features(df_orig)

    # Extract all features at index 80
    features_at_80_orig = feats_orig.iloc[80].to_dict()

    # Now create modified records where prices after index 80 are radically mutated
    records_mutated = [dict(r) for r in records_original]
    for i in range(81, n):
        records_mutated[i]["close"] = 999999.0
        records_mutated[i]["high"] = 999999.0
        records_mutated[i]["volume"] = 999999.0

    df_mut = pipeline.candles_to_dataframe(records_mutated)
    feats_mut = pipeline.compute_all_features(df_mut)
    features_at_80_mut = feats_mut.iloc[80].to_dict()

    # Verify that EVERY feature at bar 80 is strictly identical between original and mutated
    for key, val_orig in features_at_80_orig.items():
        if key in ("open_time", "close_time", "symbol", "interval", "is_closed"):
            continue
        val_mut = features_at_80_mut[key]
        if pd.isna(val_orig):
            assert pd.isna(val_mut), f"Feature {key} at bar 80 differed (expected NaN)"
        else:
            assert pytest.approx(val_orig) == val_mut, f"Look-ahead detected in feature {key} at bar 80!"


def test_feature_pipeline_unclosed_candle_exclusion():
    base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    records = [
        {
            "open_time": base_time,
            "close_time": base_time + timedelta(seconds=59),
            "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 10.0,
            "is_closed": True,
        },
        {
            "open_time": base_time + timedelta(minutes=1),
            "close_time": base_time + timedelta(minutes=1, seconds=59),
            "open": 102.0, "high": 108.0, "low": 101.0, "close": 106.0, "volume": 12.0,
            "is_closed": False,  # Open/incomplete candle
        },
    ]

    pipeline = FeaturePipeline()
    df = pipeline.candles_to_dataframe(records)
    # The open candle must be excluded
    assert len(df) == 1
    assert df["is_closed"].all()


def test_feature_pipeline_duplicate_timestamp_rejection():
    base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    records = [
        {"open_time": base_time, "close_time": base_time + timedelta(seconds=59), "open": 1.0, "high": 2.0, "low": 1.0, "close": 2.0, "volume": 1.0, "is_closed": True},
        {"open_time": base_time, "close_time": base_time + timedelta(seconds=59), "open": 1.0, "high": 2.0, "low": 1.0, "close": 2.0, "volume": 1.0, "is_closed": True},
    ]
    pipeline = FeaturePipeline()
    with pytest.raises(DataIntegrityException):
        pipeline.candles_to_dataframe(records)
