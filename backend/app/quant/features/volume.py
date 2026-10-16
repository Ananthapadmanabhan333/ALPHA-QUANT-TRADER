"""
Volume Statistics Feature Calculations.

Formulas:
- Volume SMA: SMA_V,t(N) = (1 / N) * sum_{i=0}^{N-1} V_{t-i}
- Volume Ratio: V_ratio,t(N) = V_t / SMA_V,t(N)
- Volume Z-Score: Z_V,t(N) = (V_t - mu_V,t(N)) / sigma_V,t(N)

Lookback: N periods
Warm-up Period: N periods
Timestamp Alignment: Aligned to candle close timestamp t.
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_volume_sma_doc(window: int) -> FeatureDoc:
    return FeatureDoc(
        name=f"volume_sma_{window}",
        formula=f"SMA_V,t({window}) = (1 / {window}) * sum_{{i=0}}^{{{window}-1}} V_{{t-i}}",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Simple Moving Average of trading volume over {window} bars.",
    )


def get_volume_ratio_doc(window: int) -> FeatureDoc:
    return FeatureDoc(
        name=f"volume_ratio_{window}",
        formula=f"Ratio_t({window}) = V_t / SMA_V,t({window})",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Ratio of current candle volume to {window}-bar rolling volume SMA.",
    )


def get_volume_zscore_doc(window: int) -> FeatureDoc:
    return FeatureDoc(
        name=f"volume_zscore_{window}",
        formula=f"Z_V,t({window}) = (V_t - mu_V,t({window})) / sigma_V,t({window})",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Standardized z-score of current candle volume relative to {window}-bar distribution.",
    )


def compute_volume_sma(volume: pd.Series, window: int) -> pd.Series:
    if window < 1:
        raise ValueError(f"Volume window must be >= 1, got {window}")
    sma = volume.rolling(window=window, min_periods=window).mean()
    sma.name = f"volume_sma_{window}"
    return sma


def compute_volume_ratio(volume: pd.Series, window: int) -> pd.Series:
    sma = compute_volume_sma(volume, window)
    safe_sma = sma.replace(0.0, np.nan)
    ratio = volume / safe_sma
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    ratio.name = f"volume_ratio_{window}"
    return ratio


def compute_volume_zscore(volume: pd.Series, window: int) -> pd.Series:
    if window < 2:
        raise ValueError(f"Volume zscore window must be >= 2, got {window}")
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std(ddof=1)
    safe_std = std.replace(0.0, np.nan)
    zscore = (volume - mean) / safe_std
    zscore = zscore.replace([np.inf, -np.inf], np.nan)
    zscore.name = f"volume_zscore_{window}"
    return zscore
