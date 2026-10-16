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
    """Lifespan context manager for startup validation, recovery, and graceful shutdown."""
    setup_logging()
    settings: Settings = app.state.settings
    logger.info(
        "alpha_quant_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )

    # 1. Startup validation: verify database availability
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

    # 2. Startup validation: verify market data availability
    from app.market.service import MarketDataService
    market_service = MarketDataService()
    market_health = await market_service.check_market_data_dependency()
    logger.info(
        "market_data_dependency_status",
        status=market_health.get("status"),
        connected=market_health.get("connected"),
    )

    # 3. Startup recovery: verify risk controls are intact and active
    try:
        from app.db.session import get_session_factory
        from app.paper.broker import PaperBroker
        session_factory = get_session_factory()
        async with session_factory() as session:
            broker = PaperBroker()
            account = await broker.get_or_create_default_account(session)
            risk_state = await broker.get_account_risk_state(session, account.id)
            if risk_state and risk_state.emergency_stop:
                logger.warning(
                    "startup_recovery_emergency_stop_persisted",
                    account_id=account.id,
                    reason=risk_state.kill_switch_reason,
                )
    except Exception as exc:
        logger.debug("startup_risk_recovery_skipped", detail=str(exc))

    yield

    # Graceful shutdown:
    logger.info("alpha_quant_graceful_shutdown_starting")

    # Stop paper trading orchestrator if running
    try:
        from app.orchestration.lifecycle import get_lifecycle_manager
        manager = get_lifecycle_manager()
        await manager.shutdown()
    except Exception as exc:
        logger.debug("graceful_shutdown_orchestrator_cleanup", detail=str(exc))

    # Disconnect live websocket clients
    try:
        from app.orchestration.broadcaster import get_broadcaster
        broadcaster = get_broadcaster()
        await broadcaster.disconnect_all()
    except Exception as exc:
        logger.debug("graceful_shutdown_broadcaster_cleanup", detail=str(exc))

    # Close open database pool connections
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
        from app.market.service import MarketDataService

        db_result = await check_database_connection()
        market_service = MarketDataService()
        market_result = await market_service.check_market_data_dependency()

        is_ready = bool(db_result.get("connected") and market_result.get("connected"))
        if not is_ready:
            response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

        return ReadinessResponse(
            status="ready" if is_ready else "not_ready",
            ready=is_ready,
            timestamp=datetime.now(timezone.utc),
            components={
                "database": db_result,
                "market_data": market_result,
            },
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
