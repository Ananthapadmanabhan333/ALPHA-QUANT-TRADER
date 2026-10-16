from functools import lru_cache
from typing import Any, List, Literal, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application Settings
    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = "development"
    PROJECT_NAME: str = "ALPHA Quant"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # Database Configuration (TimescaleDB / PostgreSQL)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secure_placeholder"
    POSTGRES_DB: str = "alpha_quant"

    DATABASE_URL: str | None = None
    DATABASE_SYNC_URL: str | None = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_db_connection(cls, v: str | None, values: Any) -> str:
        if isinstance(v, str) and v.strip():
            return v
        data = values.data
        user = data.get("POSTGRES_USER", "postgres")
        pwd = data.get("POSTGRES_PASSWORD", "postgres_secure_placeholder")
        server = data.get("POSTGRES_SERVER", "localhost")
        port = data.get("POSTGRES_PORT", 5432)
        db = data.get("POSTGRES_DB", "alpha_quant")
        return f"postgresql+asyncpg://{user}:{pwd}@{server}:{port}/{db}"

    @field_validator("DATABASE_SYNC_URL", mode="before")
    @classmethod
    def assemble_sync_db_connection(cls, v: str | None, values: Any) -> str:
        if isinstance(v, str) and v.strip():
            return v
        data = values.data
        async_url = data.get("DATABASE_URL")
        if isinstance(async_url, str) and "sqlite" in async_url:
            return async_url.replace("sqlite+aiosqlite://", "sqlite://")
        user = data.get("POSTGRES_USER", "postgres")
        pwd = data.get("POSTGRES_PASSWORD", "postgres_secure_placeholder")
        server = data.get("POSTGRES_SERVER", "localhost")
        port = data.get("POSTGRES_PORT", 5432)
        db = data.get("POSTGRES_DB", "alpha_quant")
        return f"postgresql+psycopg://{user}:{pwd}@{server}:{port}/{db}"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # Market Data Subsystem Configuration (Binance Spot Public)
    BINANCE_REST_BASE_URL: str = "https://api.binance.com"
    BINANCE_WS_BASE_URL: str = "wss://stream.binance.com:9443/ws"
    DEFAULT_SYMBOL: str = "BTCUSDT"
    DEFAULT_INTERVAL: str = "1m"
    MARKET_DATA_RATE_LIMIT_PER_MINUTE: int = 1200
    MARKET_DATA_WS_INITIAL_BACKOFF_SECONDS: float = 1.0
    MARKET_DATA_WS_MAX_BACKOFF_SECONDS: float = 60.0


@lru_cache()
def get_settings() -> Settings:
    return Settings()
