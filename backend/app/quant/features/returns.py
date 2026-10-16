"""
Return Feature Calculations.

Formulas:
- Simple Return: R_t = (P_t - P_{t-1}) / P_{t-1} = P_t / P_{t-1} - 1
- Logarithmic Return: r_t = ln(P_t / P_{t-1}) = ln(P_t) - ln(P_{t-1})

Lookback: 1 period (between candle t-1 and candle t)
Warm-up Period: 1 period (the first value at t=0 is NaN)
Timestamp Alignment: Aligned to candle close timestamp t.
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc


def get_simple_return_doc(prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_simple_return",
        formula="R_t = (P_t - P_{t-1}) / P_{t-1}",
        lookback=1,
        warmup_period=1,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Simple percentage return of {prefix} from candle t-1 to candle t.",
    )


def get_log_return_doc(prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_log_return",
        formula="r_t = ln(P_t / P_{t-1}) = ln(P_t) - ln(P_{t-1})",
        lookback=1,
        warmup_period=1,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Continuously compounded logarithmic return of {prefix} from candle t-1 to candle t.",
    )


def compute_simple_returns(series: pd.Series) -> pd.Series:
    """
    Computes 1-period simple returns.
    """
    returns = series.pct_change(fill_method=None)
    # Sanitize infinities if any denominator was zero
    returns = returns.replace([np.inf, -np.inf], np.nan)
    returns.name = f"{series.name}_simple_return" if series.name else "simple_return"
    return returns


def compute_log_returns(series: pd.Series) -> pd.Series:
    """
    Computes 1-period continuously compounded logarithmic returns.
    """
    if (series <= 0).any():
        raise ValueError("Log returns require strictly positive values.")
    
    log_returns = np.log(series / series.shift(1))
    log_returns = log_returns.replace([np.inf, -np.inf], np.nan)
    log_returns.name = f"{series.name}_log_return" if series.name else "log_return"
    return log_returns
