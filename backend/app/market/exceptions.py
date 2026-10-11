from typing import Any, Dict, Optional
from app.core.exceptions import AlphaQuantException


class MarketDataException(AlphaQuantException):
    def __init__(
        self,
        message: str = "Market data processing error",
        status_code: int = 500,
        error_code: str = "MARKET_DATA_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )


class InvalidIntervalException(MarketDataException):
    def __init__(self, interval: str, allowed: list[str]):
        super().__init__(
            message=f"Unsupported candle interval '{interval}'. Supported intervals: {allowed}",
            status_code=400,
            error_code="INVALID_INTERVAL",
            details={"provided_interval": interval, "supported_intervals": allowed},
        )


class InvalidSymbolException(MarketDataException):
    def __init__(self, symbol: str):
        super().__init__(
            message=f"Invalid or unsupported symbol '{symbol}'",
            status_code=400,
            error_code="INVALID_SYMBOL",
            details={"provided_symbol": symbol},
        )


class CandleValidationException(MarketDataException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Candle data integrity validation failed: {message}",
            status_code=422,
            error_code="CANDLE_VALIDATION_FAILED",
            details=details,
        )


class RateLimitExceededException(MarketDataException):
    def __init__(self, retry_after_seconds: float = 60.0):
        super().__init__(
            message="Exchange REST rate limit reached. Pausing requests.",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after_seconds": retry_after_seconds},
        )


class ExchangeConnectionException(MarketDataException):
    def __init__(self, message: str = "Failed to establish exchange connection", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code="EXCHANGE_CONNECTION_FAILED",
            details=details,
        )
