import time
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("db")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_engine(engine: AsyncEngine | None) -> None:
    """Set or override the active database engine (useful for tests)."""
    global _engine, _session_factory
    _engine = engine
    if engine is not None:
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    else:
        _session_factory = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.DATABASE_URL
        # SQLite async requires sqlite+aiosqlite://
        is_sqlite = "sqlite" in url
        engine_args: Dict[str, Any] = {
            "echo": settings.DEBUG,
            "future": True,
        }
        if not is_sqlite:
            engine_args["pool_pre_ping"] = True
            engine_args["pool_size"] = 10
            engine_args["max_overflow"] = 20

        _engine = create_async_engine(url, **engine_args)
        logger.info("db_engine_initialized", dialect=_engine.dialect.name)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection(engine_override: AsyncEngine | None = None) -> Dict[str, Any]:
    """Verify database connectivity and query responsiveness."""
    engine = engine_override or get_engine()
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "connected": True,
            "latency_ms": latency,
            "dialect": engine.dialect.name,
        }
    except Exception as exc:
        latency = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning("database_healthcheck_failed", error=str(exc), latency_ms=latency)
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": latency,
            "dialect": engine.dialect.name,
            "error": str(exc),
        }


async def close_database_connection() -> None:
    """Graceful database shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        logger.info("closing_database_engine")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_engine_closed")
