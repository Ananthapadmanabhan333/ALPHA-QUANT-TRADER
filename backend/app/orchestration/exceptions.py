"""
ALPHA Quant — Phase 6: Orchestration Subsystem Exceptions.
"""

from typing import Any, Dict, Optional
from app.core.exceptions import AlphaQuantException


class OrchestrationException(AlphaQuantException):
    """Base exception for orchestration and lifecycle manager errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "ORCHESTRATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code=status_code, error_code=error_code, details=details)


class DuplicateSchedulerException(OrchestrationException):
    """Raised when an attempt is made to launch multiple scheduler instances for the same engine."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="DUPLICATE_SCHEDULER_CONFLICT",
            details=details,
        )


class StaleMarketDataException(OrchestrationException):
    """Raised when market data is absent or older than allowed threshold during lifecycle evaluation."""
    def __init__(self, message: str = "Market data feed is stale or unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="STALE_MARKET_DATA",
            details=details,
        )


class FeaturePipelineNotReadyException(OrchestrationException):
    """Raised when insufficient candle bars exist to compute required feature lookbacks."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="FEATURE_WARMUP_INSUFFICIENT",
            details=details,
        )
