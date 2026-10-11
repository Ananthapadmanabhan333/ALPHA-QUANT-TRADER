from typing import Dict, Literal

# Supported Intervals
SUPPORTED_INTERVALS = ["1m", "5m", "15m"]
IntervalType = Literal["1m", "5m", "15m"]

# Interval Durations in Milliseconds and Seconds
INTERVAL_TO_MS: Dict[str, int] = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
}

INTERVAL_TO_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
}

# Canonical Supported Symbols
SUPPORTED_SYMBOLS = ["BTCUSDT", "BTC/USDT", "ETHUSDT", "ETH/USDT"]
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL: IntervalType = "1m"

# Default Exchange Endpoints
BINANCE_REST_BASE_URL = "https://api.binance.com"
BINANCE_WS_BASE_URL = "wss://stream.binance.com:9443/ws"

# Rate Limits
DEFAULT_MAX_WEIGHT_PER_MINUTE = 1200
DEFAULT_KLINES_LIMIT = 500
MAX_KLINES_LIMIT = 1000


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to standard exchange format, e.g. BTC/USDT -> BTCUSDT."""
    return symbol.replace("/", "").replace("-", "").replace("_", "").upper()


def format_display_symbol(symbol: str) -> str:
    """Format symbol for display, e.g. BTCUSDT -> BTC/USDT."""
    norm = normalize_symbol(symbol)
    if norm.endswith("USDT"):
        return f"{norm[:-4]}/USDT"
    elif norm.endswith("USD"):
        return f"{norm[:-3]}/USD"
    return norm
