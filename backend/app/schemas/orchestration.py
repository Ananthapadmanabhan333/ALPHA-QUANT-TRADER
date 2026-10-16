"""
ALPHA Quant — Phase 6: Orchestration & Lifecycle Schemas.
Provides typed validation contracts for lifecycle execution, task tracking, risk reset, and audit events.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PaperTradingStartRequest(BaseModel):
    """Payload to initiate automated paper trading loop."""
    strategy_id: str = Field(..., description="Target quantitative strategy (e.g. trend_following, mean_reversion, momentum)")
    symbol: str = Field("BTCUSDT", description="Market symbol (e.g. BTCUSDT or BTC/USDT)")
    interval: str = Field("1m", description="Candle bar timeframe: 1m, 5m, or 15m")
    poll_interval_seconds: float = Field(5.0, ge=0.5, le=60.0, description="Cycle execution polling interval in seconds")
    order_size_pct: float = Field(0.05, ge=0.001, le=0.10, description="Order size fraction of portfolio equity (default 5%)")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Optional custom strategy hyperparameter overrides")
    is_live: bool = Field(False, description="Explicit safety flag. Must remain False.")

    @field_validator("is_live")
    @classmethod
    def reject_live_execution(cls, v: bool) -> bool:
        if v:
            raise ValueError("Live trading is strictly prohibited. ALPHA Quant Phase 6 engine is exclusively simulation.")
        return False


class PaperTradingStartResponse(BaseModel):
    """Response confirming activation of paper trading scheduler loop."""
    status: str = Field(..., description="Orchestration status: RUNNING")
    task_id: str = Field(..., description="Unique lifecycle runner task ID")
    worker_id: str = Field(..., description="Exclusive task owner worker ID")
    strategy_id: str = Field(..., description="Active strategy ID")
    symbol: str = Field(..., description="Target market symbol")
    interval: str = Field(..., description="Bar interval")
    started_at: datetime = Field(..., description="UTC startup timestamp")
    message: str = Field(..., description="Status summary")


class PaperTradingStopResponse(BaseModel):
    """Response confirming termination of paper trading scheduler loop."""
    status: str = Field(..., description="Orchestration status: STOPPED")
    stopped_at: datetime = Field(..., description="UTC shutdown timestamp")
    total_cycles: int = Field(..., description="Total execution cycles completed")
    signals_generated: int = Field(..., description="Total quantitative signals generated")
    orders_submitted: int = Field(..., description="Total simulated paper orders submitted")
    message: str = Field(..., description="Status summary")


class PaperTradingStatusResponse(BaseModel):
    """Telemetry report for active or idle lifecycle manager."""
    status: str = Field(..., description="Current status: STOPPED, STARTING, RUNNING, PAUSED, STOPPING, ERROR")
    task_id: Optional[str] = Field(None, description="Active task ID if running")
    worker_id: str = Field(..., description="Task worker ID")
    strategy_id: Optional[str] = Field(None, description="Active strategy ID")
    symbol: str = Field(..., description="Trading symbol")
    interval: str = Field(..., description="Candle interval")
    started_at: Optional[datetime] = Field(None, description="Start time if active")
    last_cycle_at: Optional[datetime] = Field(None, description="Timestamp of most recent evaluation cycle")
    cycle_count: int = Field(0, description="Total completed cycles")
    signals_count: int = Field(0, description="Signals produced")
    orders_count: int = Field(0, description="Orders placed")
    last_error: Optional[str] = Field(None, description="Last error message if encountered")


class RiskResetRequest(BaseModel):
    """Operator authorization payload to reset tripped risk limits."""
    confirmation_code: str = Field(..., description="Mandatory confirmation token 'CONFIRM_RESET'")
    reset_emergency_stop: bool = Field(True, description="Clear emergency pause state")
    reset_consecutive_losses: bool = Field(True, description="Reset consecutive loss counter to 0")
    reset_daily_loss: bool = Field(False, description="Reset daily accumulated PnL baseline to 0.0")
    reason: Optional[str] = Field("Operator authorized risk reset", description="Audit log reason")

    @field_validator("confirmation_code")
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        if v.strip() != "CONFIRM_RESET":
            raise ValueError("Invalid confirmation code. Must be 'CONFIRM_RESET' to perform risk reset.")
        return v.strip()


class RiskResetResponse(BaseModel):
    """Response detailing updated risk state after operator reset."""
    success: bool = Field(..., description="Whether risk reset was successfully applied")
    message: str = Field(..., description="Summary of applied reset actions")
    timestamp: datetime = Field(..., description="Reset UTC timestamp")
    risk_state: Dict[str, Any] = Field(..., description="Current post-reset risk state")


class SystemEventResponse(BaseModel):
    """Immutable audit entry for risk, execution, or orchestrator lifecycle events."""
    id: str = Field(..., description="Unique event identifier")
    account_id: str = Field(..., description="Associated paper account ID")
    event_type: str = Field(..., description="Category: ORCHESTRATOR_START, ORCHESTRATOR_STOP, RISK_BREACH, etc.")
    severity: str = Field(..., description="Severity level: INFO, WARNING, CRITICAL")
    reason: str = Field(..., description="Human-readable description")
    metadata_json: Dict[str, Any] = Field(default_factory=dict, description="Structured event payload")
    created_at: datetime = Field(..., description="UTC creation timestamp")


class AsyncTaskResponse(BaseModel):
    """Status record for async background job execution (e.g. backtests)."""
    task_id: str = Field(..., description="Unique background job task ID")
    task_type: str = Field(..., description="Job classification: BACKTEST_SIMULATION")
    status: str = Field(..., description="Job state: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED")
    progress: float = Field(0.0, description="Job completion progress 0.0 - 1.0")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution output if completed")
    error: Optional[str] = Field(None, description="Failure reason if failed")
    created_at: datetime = Field(..., description="Enqueued timestamp")
    started_at: Optional[datetime] = Field(None, description="Start execution timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    message: Optional[str] = Field(None, description="Descriptive status message")
