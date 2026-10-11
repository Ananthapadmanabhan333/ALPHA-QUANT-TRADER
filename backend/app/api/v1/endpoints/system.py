import time
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.db.session import check_database_connection
from app.models.system import SystemAuditLog
from app.schemas.health import SystemInfoResponse, DatabaseHealth

router = APIRouter(prefix="/system", tags=["System Information"])

_START_TIME = time.time()


class SystemAuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    component: str
    event_type: str
    status: str
    message: str
    payload: dict | None = None
    created_at: datetime


@router.get("/status", response_model=SystemInfoResponse, summary="Detailed System Status")
async def get_system_status(settings: Settings = Depends(get_settings)) -> SystemInfoResponse:
    """Returns comprehensive system information, uptime, and database diagnostics."""
    db_result = await check_database_connection()
    uptime = round(time.time() - _START_TIME, 2)

    return SystemInfoResponse(
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=uptime,
        database=DatabaseHealth(**db_result),
    )


@router.get("/audit-logs", response_model=List[SystemAuditLogSchema], summary="System Initialization & Audit Logs")
async def get_system_audit_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> List[SystemAuditLogSchema]:
    """
    Returns authentic system audit logs from the database.
    Honest empty state: returns an empty list if no logs have been recorded yet.
    No fabricated data.
    """
    stmt = select(SystemAuditLog).order_by(desc(SystemAuditLog.created_at)).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()
    return list(records)
