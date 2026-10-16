"""
Multi-Period Momentum Feature Calculations.

Formula:
M_t(k) = (P_t - P_{t-k}) / P_{t-k} = (P_t / P_{t-k}) - 1

Lookback: k periods
Warm-up Period: k periods
Timestamp Alignment: Aligned to candle close timestamp t.
"""
from typing import Dict, List
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_momentum_doc(period: int, prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_momentum_{period}",
        formula=f"M_t({period}) = (P_t - P_{{t-{period}}}) / P_{{t-{period}}}",
        lookback=period,
        warmup_period=period,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Multi-period rate of change momentum of {prefix} over {period} bars.",
    )


def compute_momentum(series: pd.Series, period: int) -> pd.Series:
    """
    Computes momentum over k periods: (P_t - P_{t-k}) / P_{t-k}.
    """
    if period < 1:
        raise ValueError(f"Momentum period must be >= 1, got {period}")

    past = series.shift(period)
    safe_past = past.replace(0.0, np.nan)
    mom = (series - past) / safe_past
    mom = mom.replace([np.inf, -np.inf], np.nan)
    mom.name = f"{series.name}_momentum_{period}" if series.name else f"momentum_{period}"
    return mom


def compute_multi_period_momentum(
    series: pd.Series,
    periods: List[int],
) -> Dict[str, pd.Series]:
    """
    Computes momentum series across a list of periods.
    """
    results: Dict[str, pd.Series] = {}
    for p in periods:
        s = compute_momentum(series, p)
        results[s.name] = s
    return results
