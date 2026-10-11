from typing import Any, Dict, Optional


class AlphaQuantException(Exception):
    """Base exception for all Alpha Quant domain errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class DatabaseConnectionException(AlphaQuantException):
    def __init__(self, message: str = "Database connection error", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code="DATABASE_UNAVAILABLE",
            details=details,
        )


class EntityNotFoundException(AlphaQuantException):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
        )


class ConfigurationException(AlphaQuantException):
    def __init__(self, message: str = "Invalid system configuration", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="CONFIG_ERROR",
            details=details,
        )


class ValidationException(AlphaQuantException):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_FAILED",
            details=details,
        )
