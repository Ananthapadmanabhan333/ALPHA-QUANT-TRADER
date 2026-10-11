import pytest
from httpx import AsyncClient
from app.core.exceptions import EntityNotFoundException, ValidationException


@pytest.mark.asyncio
async def test_404_handling(client: AsyncClient):
    response = await client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert "timestamp" in data["error"]


@pytest.mark.asyncio
async def test_custom_domain_exception(test_app, client: AsyncClient):
    @test_app.get("/test-custom-exception")
    async def trigger_custom_exc():
        raise EntityNotFoundException("Strategy configuration not found", details={"strategy_id": "alpha-01"})

    response = await client.get("/test-custom-exception")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert data["error"]["message"] == "Strategy configuration not found"
    assert data["error"]["details"]["strategy_id"] == "alpha-01"


@pytest.mark.asyncio
async def test_validation_error_format(client: AsyncClient):
    # Pass invalid limit query parameter
    response = await client.get("/api/v1/system/audit-logs?limit=invalid_integer")
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]
