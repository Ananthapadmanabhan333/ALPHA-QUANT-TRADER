from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from app.core.config import Settings, get_settings
from app.db.session import check_database_connection
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["Health & Readiness"])


@router.get("", response_model=HealthResponse, summary="Liveness Probe")
async def health_liveness(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness probe: returns 200 if the FastAPI application process is up and running."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/liveness", response_model=HealthResponse, summary="Liveness Probe Alias")
async def liveness(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Explicit liveness probe for Kubernetes / orchestrator probes."""
    return await health_liveness(settings=settings)


from app.market.service import MarketDataService

market_service = MarketDataService()


@router.get("/readiness", response_model=ReadinessResponse, summary="Readiness Probe")
async def health_readiness(response: Response) -> ReadinessResponse:
    """Readiness probe: validates database and market data connectivity before accepting user traffic."""
    db_result = await check_database_connection()
    market_result = await market_service.check_market_data_dependency()

    is_ready = bool(db_result.get("connected") and market_result.get("connected"))

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        ready=is_ready,
        timestamp=datetime.now(timezone.utc),
        components={
            "database": db_result,
            "market_data": market_result,
        },
    )
