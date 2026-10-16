"""
Rolling Z-score Feature Calculations.

Formula:
Z_t(N) = (P_t - mu_t(N)) / sigma_t(N)
where:
- mu_t(N) = (1 / N) * sum_{i=0}^{N-1} P_{t-i} (Rolling mean over N bars)
- sigma_t(N) = sqrt( (1 / (N - 1)) * sum_{i=0}^{N-1} (P_{t-i} - mu_t(N))^2 ) (Sample rolling standard deviation)

Lookback: N periods
Warm-up Period: N periods
Timestamp Alignment: Aligned to candle close timestamp t.
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_zscore_doc(window: int, prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_zscore_{window}",
        formula=f"Z_t({window}) = (P_t - mu_t({window})) / sigma_t({window})",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Standardized rolling z-score of {prefix} relative to rolling {window}-bar distribution.",
    )


def compute_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """
    Computes rolling z-score of a price or metric series.

    Parameters:
        series: Pandas series of values.
        window: Integer lookback window (N >= 2).
    """
    if window < 2:
        raise ValueError(f"Z-score window must be >= 2, got {window}")

    mean = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std(ddof=1)

    # Avoid zero division if prices in window are flat
    safe_std = std.replace(0.0, np.nan)
    zscore = (series - mean) / safe_std
    zscore = zscore.replace([np.inf, -np.inf], np.nan)
    zscore.name = f"{series.name}_zscore_{window}" if series.name else f"zscore_{window}"
    return zscore
