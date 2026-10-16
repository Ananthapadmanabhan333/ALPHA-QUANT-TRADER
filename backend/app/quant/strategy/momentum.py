from typing import Any, Dict, List, Optional
import pandas as pd

from app.quant.constants import (
    DEFAULT_MOMENTUM_PARAMS,
    STRATEGY_MOMENTUM,
    SignalSide,
)
from app.quant.strategy.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """
    Baseline Volatility-Normalized Multi-Period Momentum Strategy:
    - Multi-period momentum returns (default lookbacks 5, 15, 60).
    - Volatility normalization: scales raw momentum by rolling return volatility.
    - Transaction cost hurdle: requires expected movement to exceed 2x estimated round-trip trading fees.
    - Explicit exits: momentum exhaustion (<= 0) or normalized momentum fading.
    - Long-only spot research.
    """

    def __init__(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
    ):
        params = {**DEFAULT_MOMENTUM_PARAMS, **(parameters or {})}
        super().__init__(
            strategy_id=STRATEGY_MOMENTUM,
            version=version,
            parameters=params,
        )
        self.windows: List[int] = list(params["momentum_windows"])
        self.vol_window: int = int(params["volatility_window"])
        self.tx_cost_bps: float = float(params["transaction_cost_bps"])
        self.cost_multiplier: float = float(params.get("cost_hurdle_multiplier", 2.0))

        # Weighting: equal or descending by lookback
        self.weights = params.get("weights")
        if not self.weights or len(self.weights) != len(self.windows):
            # Default equal weights
            self.weights = [1.0 / len(self.windows)] * len(self.windows)

    @property
    def required_warmup_period(self) -> int:
        return max(max(self.windows), self.vol_window + 1)

    @property
    def cost_hurdle(self) -> float:
        """Minimum expected movement required to clear round-trip transaction costs."""
        # 1 bp = 0.0001; round-trip is 2x; hurdle is cost_multiplier * round-trip
        single_trip = self.tx_cost_bps / 10000.0
        return self.cost_multiplier * (2.0 * single_trip)

    def evaluate_bar(
        self,
        current_bar: pd.Series,
        in_position: bool,
    ) -> tuple[SignalSide, float, str, Dict[str, Optional[float]]]:
        # Collect momentum features
        mom_values = []
        features: Dict[str, Optional[float]] = {}
        for w in self.windows:
            col = f"momentum_{w}"
            val = current_bar.get(col)
            features[col] = float(val) if pd.notna(val) else None
            mom_values.append(val)

        vol_col = f"volatility_{self.vol_window}"
        vol = current_bar.get(vol_col)
        features["volatility"] = float(vol) if pd.notna(vol) else None

        if any(pd.isna(v) for v in mom_values):
            return SignalSide.HOLD, 0.0, "Missing multi-period momentum features", features

        # Compute weighted blended momentum
        blended_mom = sum(w * float(v) for w, v in zip(self.weights, mom_values))
        features["blended_momentum"] = blended_mom

        # Volatility normalization
        curr_vol = float(vol) if pd.notna(vol) and float(vol) > 1e-6 else 1e-6
        norm_mom = blended_mom / curr_vol
        features["normalized_momentum"] = norm_mom
        features["cost_hurdle"] = self.cost_hurdle

        hurdle = self.cost_hurdle

        if not in_position:
            # Entry condition: blended momentum exceeds transaction cost hurdle and normalized momentum is positive
            if blended_mom >= hurdle and norm_mom > 0:
                score = min(1.0, max(0.1, norm_mom / 5.0))
                return (
                    SignalSide.BUY,
                    score,
                    f"Momentum entry: Blended mom {blended_mom:.4f} >= hurdle {hurdle:.4f} (Norm mom {norm_mom:.2f})",
                    features,
                )
            else:
                return (
                    SignalSide.HOLD,
                    0.0,
                    f"Momentum below hurdle: Blended mom {blended_mom:.4f} < hurdle {hurdle:.4f}",
                    features,
                )
        else:
            # Explicit exit condition: momentum reversal or exhaustion
            if blended_mom <= 0.0:
                return (
                    SignalSide.SELL,
                    -1.0,
                    f"Explicit momentum exit: Blended momentum turned non-positive ({blended_mom:.4f} <= 0.0)",
                    features,
                )
            if norm_mom < 0.2:
                return (
                    SignalSide.SELL,
                    -0.7,
                    f"Explicit momentum fade exit: Vol-normalized momentum faded ({norm_mom:.2f} < 0.2)",
                    features,
                )

            return (
                SignalSide.HOLD,
                0.5,
                f"Holding long momentum: Blended mom {blended_mom:.4f} remains positive",
                features,
            )
