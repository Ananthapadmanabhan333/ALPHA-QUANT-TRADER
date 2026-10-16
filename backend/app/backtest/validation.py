from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.backtest.constants import MarketRegime


@dataclass(frozen=True)
class DatasetPartitions:
    train: pd.DataFrame
    validation: pd.DataFrame
    holdout: pd.DataFrame
    train_range: Tuple[str, str]
    validation_range: Tuple[str, str]
    holdout_range: Tuple[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_bars": len(self.train),
            "validation_bars": len(self.validation),
            "holdout_bars": len(self.holdout),
            "train_range": self.train_range,
            "validation_range": self.validation_range,
            "holdout_range": self.holdout_range,
            "holdout_status": "UNTOUCHED_FINAL_HOLDOUT",
        }


def split_chronological(
    df: pd.DataFrame,
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    holdout_ratio: float = 0.20,
) -> DatasetPartitions:
    """
    Splits candle dataset into strictly chronological Train, Validation, and Holdout partitions.
    Guarantees that the final holdout period is strictly segregated and never leaks into training.
    """
    n = len(df)
    if n < 30:
        raise ValueError(f"Dataset too small ({n} bars) to partition into train/validation/holdout.")

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end].copy().reset_index(drop=True)
    val_df = df.iloc[train_end:val_end].copy().reset_index(drop=True)
    holdout_df = df.iloc[val_end:].copy().reset_index(drop=True)

    def get_range(d: pd.DataFrame) -> Tuple[str, str]:
        if d.empty:
            return ("", "")
        t0 = str(d["open_time"].iloc[0])
        t1 = str(d["open_time"].iloc[-1])
        return (t0, t1)

    return DatasetPartitions(
        train=train_df,
        validation=val_df,
        holdout=holdout_df,
        train_range=get_range(train_df),
        validation_range=get_range(val_df),
        holdout_range=get_range(holdout_df),
    )


def generate_walk_forward_windows(
    df: pd.DataFrame,
    train_bars: int = 100,
    test_bars: int = 30,
    step_bars: int = 30,
) -> Generator[Tuple[int, pd.DataFrame, pd.DataFrame], None, None]:
    """
    Yields rolling walk-forward train and test windows chronologically.
    """
    n = len(df)
    window_idx = 0
    start = 0

    while (start + train_bars + test_bars) <= n:
        train_slice = df.iloc[start : start + train_bars].copy().reset_index(drop=True)
        test_slice = df.iloc[start + train_bars : start + train_bars + test_bars].copy().reset_index(drop=True)
        yield window_idx, train_slice, test_slice
        window_idx += 1
        start += step_bars


def classify_market_regimes(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Classifies each bar into one of 4 regimes: BULLISH, BEARISH, HIGH_VOLATILITY, CHOPPY.
    Uses strictly backward-looking metrics.
    """
    close = df["close"]
    pct_change_20 = (close - close.shift(window)) / close.shift(window)
    vol_20 = close.pct_change(fill_method=None).rolling(window=window).std()

    vol_threshold = vol_20.quantile(0.75) if not vol_20.dropna().empty else 0.02

    regimes = []
    for i in range(len(df)):
        c_ret = pct_change_20.iloc[i]
        c_vol = vol_20.iloc[i]

        if pd.isna(c_ret) or pd.isna(c_vol):
            regimes.append(MarketRegime.CHOPPY.value)
        elif c_vol >= vol_threshold:
            regimes.append(MarketRegime.HIGH_VOLATILITY.value)
        elif c_ret >= 0.01:
            regimes.append(MarketRegime.BULLISH.value)
        elif c_ret <= -0.01:
            regimes.append(MarketRegime.BEARISH.value)
        else:
            regimes.append(MarketRegime.CHOPPY.value)

    return pd.Series(regimes, index=df.index, name="market_regime")
