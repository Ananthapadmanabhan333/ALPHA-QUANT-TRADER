"""
Moving Average Feature Calculations.

Formulas:
- SMA_t(N) = (1 / N) * sum_{i=0}^{N-1} P_{t-i}
- EMA_t(N) = alpha * P_t + (1 - alpha) * EMA_{t-1}(N), where alpha = 2 / (N + 1)

Lookback: N periods
Warm-up Period: N periods (first N - 1 values are NaN)
Timestamp Alignment: Aligned to candle close timestamp t (backward-looking only)
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_sma_doc(window: int, prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_sma_{window}",
        formula=f"SMA_t({window}) = (1 / {window}) * sum_{{i=0}}^{{{window}-1}} P_{{t-i}}",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Simple Moving Average of {prefix} over {window} bars.",
    )


def get_ema_doc(window: int, prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_ema_{window}",
        formula=f"EMA_t({window}) = alpha * P_t + (1 - alpha) * EMA_{{t-1}}({window}), alpha = 2 / ({window} + 1)",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Exponential Moving Average of {prefix} over {window} bars.",
    )


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """
    Computes Simple Moving Average (SMA).

    Parameters:
        series: Pandas series of prices (chronologically sorted).
        window: Integer window lookback (N >= 1).

    Returns:
        Pandas series with SMA values. The first N - 1 entries are NaN.
    """
    if window < 1:
        raise ValueError(f"Window must be >= 1, got {window}")
    
    # Strictly backward-looking rolling mean
    sma = series.rolling(window=window, min_periods=window).mean()
    sma.name = f"{series.name}_sma_{window}" if series.name else f"sma_{window}"
    return sma


def compute_ema(series: pd.Series, window: int) -> pd.Series:
    """
    Computes Exponential Moving Average (EMA).

    Parameters:
        series: Pandas series of prices (chronologically sorted).
        window: Integer window lookback (N >= 1).

    Returns:
        Pandas series with EMA values. Strictly masks first N - 1 values as NaN for warm-up.
    """
    if window < 1:
        raise ValueError(f"Window must be >= 1, got {window}")

    # EWM with adjust=False implements standard recursive EMA: EMA_t = alpha * P_t + (1 - alpha) * EMA_{t-1}
    ema = series.ewm(span=window, adjust=False).mean()

    # Mask initial un-warmed values to prevent un-warmed signal generation
    if len(ema) > 0 and window > 1:
        ema.iloc[: window - 1] = np.nan

    ema.name = f"{series.name}_ema_{window}" if series.name else f"ema_{window}"
    return ema
