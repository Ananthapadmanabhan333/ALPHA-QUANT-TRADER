"""
ALPHA Quant — Phase 5: Paper Execution and Risk Constants.
Institutional simulation parameters, risk thresholds, and order states.
"""

from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class RiskEventSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskEventType(str, Enum):
    EMERGENCY_STOP = "EMERGENCY_STOP"
    EMERGENCY_RESUME = "EMERGENCY_RESUME"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    STALE_FEED = "STALE_FEED"
    RECONCILIATION_FAILURE = "RECONCILIATION_FAILURE"
    UNAUTHORIZED_CONFIGURATION = "UNAUTHORIZED_CONFIGURATION"


# ==========================================
# Illustrative & Configurable Default Risk Limits
# ==========================================
# All limits are explicitly documented and enforced by the Central Risk Gate.
DEFAULT_INITIAL_CASH = 10000.0  # Virtual USDT
DEFAULT_MAX_ORDER_NOTIONAL = 10000.0  # Max notional per single order ($ USD)
DEFAULT_MAX_POSITION_PCT = 0.10  # Max position size as fraction of virtual equity (10%)
DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT = 0.80  # Max total aggregate position exposure (80%)
DEFAULT_DAILY_LOSS_LIMIT_PCT = 0.02  # Max allowable daily equity loss (2% of starting daily equity)
DEFAULT_MAX_DRAWDOWN_LIMIT_PCT = 0.05  # Max allowable peak-to-trough equity drawdown (5%)
DEFAULT_CONSECUTIVE_LOSS_LIMIT = 3  # Max consecutive losing trades before entry blocking
DEFAULT_MAX_FEED_AGE_SECONDS = 300.0  # Maximum tolerated age for market data observations (5 min)
DEFAULT_MAX_SPREAD_BPS = 50.0  # Reject orders if bid-ask spread exceeds 50 basis points
DEFAULT_MAX_LIQUIDITY_PARTICIPATION_PCT = 0.10  # Max fill quantity per bar (10% of bar volume)

# Default Fee and Slippage Schedules (Institutional Long-Only Spot)
DEFAULT_MAKER_FEE_BPS = 8.0  # 0.08%
DEFAULT_TAKER_FEE_BPS = 10.0  # 0.10%
DEFAULT_SLIPPAGE_BPS = 5.0  # 0.05%
MIN_ORDER_NOTIONAL_USD = 10.0  # Binance Spot min notional equivalent ($10 USD)
