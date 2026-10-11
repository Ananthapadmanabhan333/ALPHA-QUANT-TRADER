from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exceptions import AlphaQuantException
from app.core.logging import get_logger

logger = get_logger("exceptions")


def format_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict | list | None = None,
    path: str | None = None,
) -> JSONResponse:
    content = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
            "path": path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    return JSONResponse(status_code=status_code, content=content)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AlphaQuantException)
    async def alpha_quant_exception_handler(request: Request, exc: AlphaQuantException) -> JSONResponse:
        logger.warning(
            "domain_exception",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            path=str(request.url),
        )
        return format_error_response(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            path=request.url.path,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.info(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=str(request.url),
        )
        return format_error_response(
            status_code=exc.status_code,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            path=request.url.path,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "validation_error",
            errors=exc.errors(),
            path=str(request.url),
        )
        return format_error_response(
            status_code=422,
            error_code="VALIDATION_ERROR",
            message="Request parameter validation failed",
            details=exc.errors(),
            path=request.url.path,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            path=str(request.url),
        )
        return format_error_response(
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
            path=request.url.path,
        )
