"""
Rolling Volatility Feature Calculations.

Formula:
sigma_t(N) = sqrt( (1 / (N - 1)) * sum_{i=0}^{N-1} (r_{t-i} - mean(r_t))^2 )
where r_t is the logarithmic return ln(P_t / P_{t-1}).

Lookback: N return periods
Warm-up Period: N + 1 price bars (1 bar for initial return, then N returns)
Timestamp Alignment: Aligned to candle close timestamp t.
"""
import numpy as np
import pandas as pd
from app.quant.features.metadata import FeatureDoc
from app.quant.features.returns import compute_log_returns


def get_volatility_doc(window: int, prefix: str = "close") -> FeatureDoc:
    return FeatureDoc(
        name=f"{prefix}_volatility_{window}",
        formula=f"sigma_t({window}) = sqrt((1/({window}-1)) * sum_{{i=0}}^{{{window}-1}} (r_{{t-i}} - mean(r_t))^2)",
        lookback=window,
        warmup_period=window + 1,
        timestamp_alignment="Aligned to the closing timestamp of candle t. Uses strictly observations up to and including t.",
        description=f"Sample standard deviation of log returns over rolling {window}-bar lookback.",
    )


def compute_rolling_volatility(
    series: pd.Series,
    window: int,
    annualization_factor: float = 1.0,
) -> pd.Series:
    """
    Computes sample rolling volatility of logarithmic returns.

    Parameters:
        series: Pandas series of prices.
        window: Number of return periods (N >= 2).
        annualization_factor: Optional scaling factor (default 1.0 for per-period volatility).
    """
    if window < 2:
        raise ValueError(f"Volatility window must be >= 2, got {window}")

    log_rets = compute_log_returns(series)
    # Rolling standard deviation with ddof=1 (unbiased sample std)
    roll_std = log_rets.rolling(window=window, min_periods=window).std(ddof=1)
    
    if annualization_factor != 1.0:
        roll_std = roll_std * np.sqrt(annualization_factor)

    roll_std = roll_std.replace([np.inf, -np.inf], np.nan)
    roll_std.name = f"{series.name}_volatility_{window}" if series.name else f"volatility_{window}"
    return roll_std
