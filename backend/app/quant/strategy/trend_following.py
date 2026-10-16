from typing import Any, Dict, Optional
import pandas as pd

from app.quant.constants import (
    DEFAULT_TREND_FOLLOWING_PARAMS,
    STRATEGY_TREND_FOLLOWING,
    SignalSide,
)
from app.quant.strategy.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """
    Baseline Trend Following Strategy:
    - Moving average windows: fast (default 20) and slow (default 100).
    - Volatility filter: suppresses entry when rolling volatility exceeds threshold.
    - Explicit exit conditions: fast MA crosses below slow MA or extreme volatility blowout.
    - Long-only spot research.
    """

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
    ):
        params = {**DEFAULT_TREND_FOLLOWING_PARAMS, **(parameters or {})}
        super().__init__(
            strategy_id=STRATEGY_TREND_FOLLOWING,
            version=version,
            parameters=params,
        )
        self.fast_window = int(params["fast_window"])
        self.slow_window = int(params["slow_window"])
        self.volatility_window = int(params["volatility_window"])
        self.max_volatility = float(params["max_volatility"])

    @property
    def required_warmup_period(self) -> int:
        return max(self.slow_window, self.volatility_window + 1)

    def evaluate_bar(
        self,
        current_bar: pd.Series,
        in_position: bool,
    ) -> tuple[SignalSide, float, str, Dict[str, Optional[float]]]:
        fast_col = f"sma_{self.fast_window}"
        slow_col = f"sma_{self.slow_window}"
        vol_col = f"volatility_{self.volatility_window}"

        fast_ma = current_bar.get(fast_col)
        slow_ma = current_bar.get(slow_col)
        vol = current_bar.get(vol_col)

        features = {
            "fast_sma": float(fast_ma) if pd.notna(fast_ma) else None,
            "slow_sma": float(slow_ma) if pd.notna(slow_ma) else None,
            "volatility": float(vol) if pd.notna(vol) else None,
        }

        if pd.isna(fast_ma) or pd.isna(slow_ma):
            return SignalSide.HOLD, 0.0, "Missing moving average features", features

        current_vol = float(vol) if pd.notna(vol) else 0.0

        if not in_position:
            # Entry condition: Fast MA > Slow MA and volatility within safe threshold
            if fast_ma > slow_ma:
                if current_vol <= self.max_volatility:
                    spread_pct = (fast_ma - slow_ma) / slow_ma
                    score = min(1.0, max(0.1, spread_pct * 100.0))
                    return (
                        SignalSide.BUY,
                        score,
                        f"Trend entry: Fast MA {fast_ma:.2f} > Slow MA {slow_ma:.2f} with vol {current_vol:.4f} <= {self.max_volatility}",
                        features,
                    )
                else:
                    return (
                        SignalSide.HOLD,
                        0.0,
                        f"Trend signal filtered: Volatility {current_vol:.4f} exceeds threshold {self.max_volatility}",
                        features,
                    )
            return SignalSide.HOLD, 0.0, "No trend alignment (Fast MA <= Slow MA)", features

        else:
            # Explicit exit condition: Fast MA crosses below Slow MA
            if fast_ma < slow_ma:
                return (
                    SignalSide.SELL,
                    -1.0,
                    f"Explicit trend exit: Fast MA {fast_ma:.2f} crossed below Slow MA {slow_ma:.2f}",
                    features,
                )
            # Volatility blowout exit
            if current_vol > (self.max_volatility * 1.5):
                return (
                    SignalSide.SELL,
                    -0.8,
                    f"Explicit volatility stop: Volatility spike {current_vol:.4f} > {self.max_volatility * 1.5:.4f}",
                    features,
                )

            return (
                SignalSide.HOLD,
                0.5,
                f"Holding long trend: Fast MA {fast_ma:.2f} remains above Slow MA {slow_ma:.2f}",
                features,
            )
