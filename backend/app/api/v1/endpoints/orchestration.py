"""
ALPHA Quant — Phase 6: Orchestration and Lifecycle REST Endpoints.
Coordinates automated paper trading lifecycle, risk reset controls, event audit logs, and async background tasks.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_key
from app.db.session import get_db
from app.orchestration.broadcaster import get_broadcaster
from app.orchestration.exceptions import DuplicateSchedulerException
from app.orchestration.lifecycle import get_lifecycle_manager
from app.orchestration.tasks import get_task_manager
from app.paper.exceptions import InvalidOrderException
from app.paper.service import PaperService
from app.schemas.orchestration import (
    AsyncTaskResponse,
    PaperTradingStartRequest,
    PaperTradingStartResponse,
    PaperTradingStatusResponse,
    PaperTradingStopResponse,
    RiskResetRequest,
    RiskResetResponse,
    SystemEventResponse,
)
from app.schemas.pagination import PaginatedResponse

router = APIRouter()
paper_service = PaperService()


@router.post(
    "/paper-trading/start",
    response_model=PaperTradingStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start automated paper trading execution loop",
)
async def start_paper_trading(
    payload: PaperTradingStartRequest,
    _auth: dict = Depends(verify_admin_key),
):
    """
    Initiates automated lifecycle execution for the requested quantitative strategy.
    Safety Invariants:
    1. Authenticated operation.
    2. Strictly simulated paper execution (live execution forbidden).
    3. Rejects duplicate scheduler instances with HTTP 409 Conflict.
    """
    manager = get_lifecycle_manager()
    try:
        result = await manager.start(
            strategy_id=payload.strategy_id,
            symbol=payload.symbol,
            interval=payload.interval,
            poll_interval_seconds=payload.poll_interval_seconds,
            order_size_pct=payload.order_size_pct,
            parameters=payload.parameters,
        )
        return PaperTradingStartResponse(**result)
    except DuplicateSchedulerException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "DUPLICATE_SCHEDULER", "message": str(exc), "details": exc.details},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/paper-trading/stop",
    response_model=PaperTradingStopResponse,
    summary="Stop automated paper trading execution loop",
)
async def stop_paper_trading(
    _auth: dict = Depends(verify_admin_key),
):
    """
    Gracefully stops the paper trading loop, drains execution tasks, and releases ownership lock.
    """
    manager = get_lifecycle_manager()
    result = await manager.stop()
    return PaperTradingStopResponse(**result)


@router.get(
    "/paper-trading/status",
    response_model=PaperTradingStatusResponse,
    summary="Get paper trading orchestrator status & telemetry",
)
async def get_paper_trading_status():
    """
    Returns real-time operational status, cycle counts, signals count, and active strategy ID.
    """
    manager = get_lifecycle_manager()
    return PaperTradingStatusResponse(**manager.get_status())


@router.post(
    "/risk/reset",
    response_model=RiskResetResponse,
    summary="Operator risk control reset with authorization",
)
async def reset_risk_controls(
    payload: RiskResetRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(verify_admin_key),
):
    """
    Operator authorized reset of tripped risk limits (emergency stop, consecutive losses, daily loss).
    Requires 'CONFIRM_RESET' code and writes an immutable audit record.
    """
    try:
        updated_state = await paper_service.reset_risk_limits(
            db=db,
            confirmation_code=payload.confirmation_code,
            reset_emergency_stop=payload.reset_emergency_stop,
            reset_consecutive_losses=payload.reset_consecutive_losses,
            reset_daily_loss=payload.reset_daily_loss,
            reason=payload.reason,
        )
        from datetime import datetime, timezone
        return RiskResetResponse(
            success=True,
            message="Risk controls successfully reset by operator authorization.",
            timestamp=datetime.now(timezone.utc),
            risk_state=updated_state.model_dump(),
        )
    except InvalidOrderException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/events",
    response_model=PaginatedResponse[SystemEventResponse],
    summary="List system, risk, and orchestrator lifecycle events",
)
async def list_system_events(
    severity: Optional[str] = Query(None, description="Filter: INFO, WARNING, CRITICAL"),
    event_type: Optional[str] = Query(None, description="Filter: ORCHESTRATOR_START, RISK_BREACH, etc."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated audit trail of system events, risk gate breaches, and execution summaries.
    """
    total, items = await paper_service.list_events_paginated(
        db=db,
        severity=severity,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    event_schemas = [
        SystemEventResponse(
            id=item["id"],
            account_id=item["account_id"],
            event_type=item["event_type"],
            severity=item["severity"],
            reason=item["reason"],
            metadata_json=item["metadata_json"],
            created_at=item["created_at"],
        )
        for item in items
    ]
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=event_schemas)


@router.get(
    "/tasks/{task_id}",
    response_model=AsyncTaskResponse,
    summary="Get background task execution status",
)
async def get_background_task_status(task_id: str):
    """
    Queries execution progress and results for async backtest or quantitative background tasks.
    """
    task_manager = get_task_manager()
    record = task_manager.get_task(task_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background task '{task_id}' not found.",
        )
    return AsyncTaskResponse(**record.to_dict())
