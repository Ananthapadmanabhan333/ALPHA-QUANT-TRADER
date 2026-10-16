from app.core.exceptions import AlphaQuantException


class QuantException(AlphaQuantException):
    """Base exception for quantitative and feature engineering domain."""
    pass


class InsufficientDataException(QuantException):
    """Raised when candle sample size is smaller than required warm-up period."""
    pass


class LookAheadBiasException(QuantException):
    """Raised when feature or strategy access future observations."""
    pass


class DataIntegrityException(QuantException):
    """Raised when data exhibits invalid ordering, gaps, or unfinalized candles."""
    pass


class FeatureCalculationException(QuantException):
    """Raised when calculation encounters math anomalies, unhandled NaNs or infinite values."""
    pass
