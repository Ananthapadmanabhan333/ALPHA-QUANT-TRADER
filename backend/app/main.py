import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.session import check_database_connection, close_database_connection
from app.schemas.health import HealthResponse, ReadinessResponse

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup validation and graceful shutdown."""
    setup_logging()
    settings: Settings = app.state.settings
    logger.info(
        "alpha_quant_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )

    # Startup validation: verify database availability
    db_health = await check_database_connection()
    if db_health.get("connected"):
        logger.info(
            "database_connected",
            dialect=db_health.get("dialect"),
            latency_ms=db_health.get("latency_ms"),
        )
    else:
        logger.warning(
            "database_offline_or_starting",
            dialect=db_health.get("dialect"),
            error=db_health.get("error"),
        )

    yield

    # Graceful shutdown: close open database pool connections
    logger.info("alpha_quant_graceful_shutdown_starting")
    await close_database_connection()
    logger.info("alpha_quant_graceful_shutdown_completed")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for ALPHA Quant FastAPI service."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="ALPHA Quant Institutional Grade Quantitative Engine & Trading Core",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Store settings on state
    app.state.settings = settings

    # Central Exception Handling
    register_exception_handlers(app)

    # CORS Middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Structured Request Logging Middleware
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Log request at info level, skip root health logs if in production
        if not (request.url.path == "/health" and settings.ENVIRONMENT == "production"):
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        return response

    # Mount versioned API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Root Level Health and Readiness Probes
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Root Liveness Probe",
    )
    async def root_health() -> HealthResponse:
        from datetime import datetime, timezone
        return HealthResponse(
            status="healthy",
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            timestamp=datetime.now(timezone.utc),
        )

    @app.get(
        "/ready",
        response_model=ReadinessResponse,
        tags=["System"],
        summary="Root Readiness Probe",
    )
    async def root_ready(response: Response) -> ReadinessResponse:
        from datetime import datetime, timezone
        from fastapi import status as http_status
        db_result = await check_database_connection()
        is_ready = db_result["connected"]
        if not is_ready:
            response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

        return ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            ready=is_ready,
            timestamp=datetime.now(timezone.utc),
            components={"database": db_result},
        )

    @app.get("/", tags=["System"], summary="Root Information")
    async def root_info() -> dict:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "status": "operational",
            "api_v1": settings.API_V1_STR,
        }

    return app


# Default app instance for ASGI runners (uvicorn)
app = create_app()
