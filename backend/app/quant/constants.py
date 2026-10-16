from enum import Enum


class SignalSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


STRATEGY_TREND_FOLLOWING = "trend_following"
STRATEGY_MEAN_REVERSION = "mean_reversion"
STRATEGY_MOMENTUM = "momentum"

SUPPORTED_STRATEGIES = (
    STRATEGY_TREND_FOLLOWING,
    STRATEGY_MEAN_REVERSION,
    STRATEGY_MOMENTUM,
)

# Baseline Default Parameters
DEFAULT_TREND_FOLLOWING_PARAMS = {
    "fast_window": 20,
    "slow_window": 100,
    "volatility_window": 20,
    "max_volatility": 0.05,
}

DEFAULT_MEAN_REVERSION_PARAMS = {
    "lookback": 60,
    "zscore_entry_threshold": 2.0,
    "zscore_exit_threshold": 0.0,
    "trend_filter_window": 100,
}

DEFAULT_MOMENTUM_PARAMS = {
    "momentum_windows": [5, 15, 60],
    "volatility_window": 20,
    "transaction_cost_bps": 10.0,
    "cost_hurdle_multiplier": 2.0,
}
