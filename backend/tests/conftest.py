from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db, set_engine
from app.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        ENVIRONMENT="testing",
        PROJECT_NAME="ALPHA Quant Test",
        VERSION="1.0.0-test",
        DEBUG=True,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_SYNC_URL="sqlite:///:memory:",
        LOG_LEVEL="DEBUG",
        LOG_FORMAT="text",
    )


@pytest_asyncio.fixture(scope="function")
async def test_engine(test_settings: Settings):
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    set_engine(engine)
    yield engine

    set_engine(None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def test_app(test_settings: Settings, test_engine):
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings

    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac
