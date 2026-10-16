from app.core.exceptions import AlphaQuantException


class BacktestException(AlphaQuantException):
    """Base exception for backtesting engine."""
    pass


class InsufficientCapitalException(BacktestException):
    """Raised when available cash balance is insufficient to place order."""
    pass


class OrderRejectedException(BacktestException):
    """Raised when an order violates liquidity, notional or price constraints."""
    pass


class InvalidOrderException(BacktestException):
    """Raised when an order has invalid parameter configurations."""
    pass


class LookAheadBacktestException(BacktestException):
    """Raised when future bar data is accessed during event evaluation."""
    pass
