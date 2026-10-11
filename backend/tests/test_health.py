import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_index(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ALPHA Quant Test"
    assert data["status"] == "operational"
    assert data["api_v1"] == "/api/v1"


@pytest.mark.asyncio
async def test_root_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "1.0.0-test"


@pytest.mark.asyncio
async def test_api_v1_health(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0-test"


@pytest.mark.asyncio
async def test_api_v1_health_liveness(client: AsyncClient):
    response = await client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_v1_health_readiness(client: AsyncClient):
    response = await client.get("/api/v1/health/readiness")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "database" in data["components"]
