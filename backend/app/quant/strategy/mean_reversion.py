from typing import Any, Dict, Optional
import pandas as pd

from app.quant.constants import (
    DEFAULT_MEAN_REVERSION_PARAMS,
    STRATEGY_MEAN_REVERSION,
    SignalSide,
)
from app.quant.strategy.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Baseline Mean Reversion Strategy:
    - Lookback: 60-candle rolling window.
    - Entry: absolute z-score threshold >= 2.0 (specifically oversold Z <= -2.0 for long spot).
    - Regime filter: verifies broader market is not in freefall (price >= 0.90 * trend_ma).
    - Explicit exits: mean reversion to mean (Z >= 0.0) or adverse stop loss (Z <= -3.5).
    - Long-only spot research.
    """

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
    ):
        params = {**DEFAULT_MEAN_REVERSION_PARAMS, **(parameters or {})}
        super().__init__(
            strategy_id=STRATEGY_MEAN_REVERSION,
            version=version,
            parameters=params,
        )
        self.lookback = int(params["lookback"])
        self.zscore_entry = abs(float(params["zscore_entry_threshold"]))
        self.zscore_exit = float(params["zscore_exit_threshold"])
        self.trend_filter_window = int(params.get("trend_filter_window", 100))
        self.stop_loss_zscore = float(params.get("stop_loss_zscore", -3.5))

    @property
    def required_warmup_period(self) -> int:
        return max(self.lookback, self.trend_filter_window)

    def evaluate_bar(
        self,
        current_bar: pd.Series,
        in_position: bool,
    ) -> tuple[SignalSide, float, str, Dict[str, Optional[float]]]:
        z_col = f"zscore_{self.lookback}"
        trend_col = f"sma_{self.trend_filter_window}"

        zscore = current_bar.get(z_col)
        trend_ma = current_bar.get(trend_col)
        close = current_bar.get("close")

        features = {
            "zscore": float(zscore) if pd.notna(zscore) else None,
            "trend_sma": float(trend_ma) if pd.notna(trend_ma) else None,
            "close": float(close) if pd.notna(close) else None,
        }

        if pd.isna(zscore) or pd.isna(close):
            return SignalSide.HOLD, 0.0, "Missing z-score features", features

        current_z = float(zscore)
        current_close = float(close)
        current_trend = float(trend_ma) if pd.notna(trend_ma) else current_close

        if not in_position:
            # Entry condition: oversold below negative threshold
            if current_z <= -self.zscore_entry:
                # Regime filter: ensure price is not more than 10% below long-term trend MA (avoid catching falling knives)
                regime_ok = current_close >= (current_trend * 0.90)
                if regime_ok:
                    score = min(1.0, abs(current_z) / 4.0)
                    return (
                        SignalSide.BUY,
                        score,
                        f"Mean reversion entry: Z-score {current_z:.2f} <= -{self.zscore_entry:.1f} in valid regime",
                        features,
                    )
                else:
                    return (
                        SignalSide.HOLD,
                        0.0,
                        f"Mean reversion suppressed: Regime failure (Price {current_close:.2f} < 0.90 * Trend MA {current_trend:.2f})",
                        features,
                    )
            return SignalSide.HOLD, 0.0, f"Z-score {current_z:.2f} within normal band (-{self.zscore_entry:.1f}, {self.zscore_entry:.1f})", features

        else:
            # Explicit exit condition: price reverted to mean
            if current_z >= self.zscore_exit:
                return (
                    SignalSide.SELL,
                    -1.0,
                    f"Explicit mean exit: Z-score {current_z:.2f} reverted to target >= {self.zscore_exit:.1f}",
                    features,
                )
            # Explicit adverse stop exit
            if current_z < self.stop_loss_zscore:
                return (
                    SignalSide.SELL,
                    -1.0,
                    f"Explicit stop exit: Z-score {current_z:.2f} breached breakdown threshold {self.stop_loss_zscore:.1f}",
                    features,
                )

            return (
                SignalSide.HOLD,
                0.5,
                f"Holding long awaiting reversion: Z-score {current_z:.2f} < {self.zscore_exit:.1f}",
                features,
            )
