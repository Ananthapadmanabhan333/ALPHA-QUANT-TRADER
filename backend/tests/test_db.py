import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import check_database_connection
from app.models.system import SystemAuditLog


@pytest.mark.asyncio
async def test_database_connection_check(test_engine):
    result = await check_database_connection()
    assert result["connected"] is True
    assert result["status"] == "healthy"
    assert "latency_ms" in result
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_system_audit_log_crud(test_session: AsyncSession):
    entry = SystemAuditLog(
        component="DATABASE",
        event_type="HEALTH_PROBE",
        status="OK",
        message="Database connectivity verified.",
        payload={"ping": "pong"},
    )
    test_session.add(entry)
    await test_session.commit()
    await test_session.refresh(entry)

    assert entry.id is not None
    assert entry.component == "DATABASE"
    assert entry.created_at is not None
    assert entry.updated_at is not None

    stmt = select(SystemAuditLog).where(SystemAuditLog.id == entry.id)
    res = await test_session.execute(stmt)
    fetched = res.scalar_one_or_none()
    assert fetched is not None
    assert fetched.message == "Database connectivity verified."
