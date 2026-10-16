from enum import Enum
from typing import Dict, Any


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class BacktestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MarketRegime(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    CHOPPY = "choppy"
    HIGH_VOLATILITY = "high_volatility"


# Default institutional spot cost assumptions
DEFAULT_COST_MODEL = {
    "maker_fee_bps": 8.0,      # 0.08%
    "taker_fee_bps": 10.0,     # 0.10%
    "slippage_bps": 5.0,       # 0.05% adverse slippage on market orders
    "assumed_spread_bps": 2.0, # 0.02% estimated top-of-book half-spread
    "max_volume_pct": 10.0,    # Max 10% participation rate of bar volume (liquidity constraint)
}

# Stress-test scenarios
STRESS_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "baseline": DEFAULT_COST_MODEL,
    "high_fee_2x": {
        **DEFAULT_COST_MODEL,
        "maker_fee_bps": 16.0,
        "taker_fee_bps": 20.0,
    },
    "high_fee_5x": {
        **DEFAULT_COST_MODEL,
        "maker_fee_bps": 40.0,
        "taker_fee_bps": 50.0,
    },
    "high_slippage_3x": {
        **DEFAULT_COST_MODEL,
        "slippage_bps": 15.0,
    },
    "severe_stress": {
        **DEFAULT_COST_MODEL,
        "taker_fee_bps": 25.0,
        "slippage_bps": 20.0,
        "assumed_spread_bps": 5.0,
    },
}
