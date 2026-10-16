"""
Average True Range (ATR) Feature Calculations.

Formulas:
- True Range: TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)
  For bar 0 (no previous close): TR_0 = H_0 - L_0.
- Average True Range: ATR_t(N) = (1 / N) * sum_{i=0}^{N-1} TR_{t-i} (or Wilder's RMA)

Lookback: N periods
Warm-up Period: N periods
Timestamp Alignment: Aligned to candle close timestamp t.
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_atr_doc(window: int) -> FeatureDoc:
    return FeatureDoc(
        name=f"atr_{window}",
        formula=f"TR_t = max(H_t - L_t, |H_t - C_{{t-1}}|, |L_t - C_{{t-1}}|); ATR_t({window}) = SMA(TR, {window})",
        lookback=window,
        warmup_period=window,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Average True Range volatility indicator over {window} bars.",
    )


def compute_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """
    Computes True Range for each bar.
    TR_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)
    """
    prev_close = close.shift(1)
    hl = high - low
    hc = (high - prev_close).abs()
    lc = (low - prev_close).abs()

    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    # For first bar without prior close, TR is high - low
    if len(tr) > 0 and pd.isna(tr.iloc[0]):
        tr.iloc[0] = hl.iloc[0]
    tr.name = "true_range"
    return tr


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """
    Computes Average True Range over specified window using rolling mean.

    Parameters:
        high: Pandas series of high prices.
        low: Pandas series of low prices.
        close: Pandas series of close prices.
        window: Integer lookback window (N >= 1).
    """
    if window < 1:
        raise ValueError(f"ATR window must be >= 1, got {window}")

    tr = compute_true_range(high, low, close)
    atr = tr.rolling(window=window, min_periods=window).mean()
    atr.name = f"atr_{window}"
    return atr
