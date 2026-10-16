"""
Domain exceptions for ALPHA Quant Phase 5 Paper Execution & Risk Subsystem.
"""

from typing import Any, Dict, Optional


class PaperExecutionException(Exception):
    """Base exception for all paper broker execution errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InsufficientBalanceException(PaperExecutionException):
    """Raised when an account lacks sufficient cash or position inventory."""
    pass


class DuplicateOrderException(PaperExecutionException):
    """Raised when an order submission violates idempotency (duplicate client_order_id)."""
    pass


class OrderNotFoundException(PaperExecutionException):
    """Raised when an order ID does not exist in the database."""
    pass


class InvalidOrderException(PaperExecutionException):
    """Raised when an order specification has invalid quantity, price, or notional."""
    pass


class RiskBreachException(PaperExecutionException):
    """Raised when an order violates one or more Central Risk Gate rules."""

    def __init__(self, rule_name: str, message: str, current_value: Any, limit_value: Any):
        details = {
            "rule_name": rule_name,
            "current_value": current_value,
            "limit_value": limit_value,
        }
        super().__init__(f"Risk Gate Breach [{rule_name}]: {message}", details=details)
        self.rule_name = rule_name
        self.current_value = current_value
        self.limit_value = limit_value


class EmergencyStopActiveException(PaperExecutionException):
    """Raised when orders are submitted while the Emergency Stop / Kill Switch is active."""
    pass


class StaleFeedException(PaperExecutionException):
    """Raised when market data exceeds the freshness threshold."""
    pass


class LiveTradingForbiddenException(PaperExecutionException):
    """Safety Invariant: Raised if any code attempts live execution or credentials."""
    pass


class ReconciliationException(PaperExecutionException):
    """Raised when ledger reconciliation detects balance or position discrepancy."""
    pass
