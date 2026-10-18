from app.core.config import Settings


def test_settings_default_values():
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        PROJECT_NAME="ALPHA Quant",
        VERSION="1.0.0",
    )
    assert settings.PROJECT_NAME == "ALPHA Quant"
    assert settings.VERSION == "1.0.0"
    assert settings.API_V1_STR == "/api/v1"
    assert "postgresql+asyncpg" in settings.DATABASE_URL
    assert "postgresql+psycopg" in settings.DATABASE_SYNC_URL


def test_cors_origin_parsing():
    settings = Settings(
        BACKEND_CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]
    )
    assert len(settings.BACKEND_CORS_ORIGINS) == 2
    assert "http://localhost:5173" in settings.BACKEND_CORS_ORIGINS


def test_database_url_override():
    custom_url = "sqlite+aiosqlite:///custom.db"
    settings = Settings(DATABASE_URL=custom_url)
    assert settings.DATABASE_URL == custom_url
