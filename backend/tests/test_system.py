import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system import SystemAuditLog


@pytest.mark.asyncio
async def test_system_status_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "ALPHA Quant Test"
    assert data["version"] == "1.0.0-test"
    assert "uptime_seconds" in data
    assert "database" in data
    assert "status" in data["database"]


@pytest.mark.asyncio
async def test_system_audit_logs_empty_state(client: AsyncClient):
    """Verifies honest empty state: returns empty array when no logs exist."""
    response = await client.get("/api/v1/system/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_system_audit_logs_with_record(client: AsyncClient, test_session: AsyncSession):
    """Verifies that actual persisted records are retrieved without fabrication."""
    log_entry = SystemAuditLog(
        component="SYSTEM_CORE",
        event_type="PHASE_1_BOOTSTRAP",
        status="SUCCESS",
        message="Phase 1 Foundation initialized successfully.",
        payload={"phase": 1, "test": True},
    )
    test_session.add(log_entry)
    await test_session.commit()

    response = await client.get("/api/v1/system/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["component"] == "SYSTEM_CORE"
    assert data[0]["event_type"] == "PHASE_1_BOOTSTRAP"
    assert data[0]["status"] == "SUCCESS"
