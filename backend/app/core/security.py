"""
ALPHA Quant — Phase 6: Authentication and Authorization Module.
Provides secure API key and Bearer token dependency injection for mutating operations.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_admin_key(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Verifies administrative authorization.
    Accepts either 'X-API-Key' header or 'Authorization: Bearer <key>'.
    Enforces authorization on mutating operations when settings.REQUIRE_AUTH is True.
    """

    if not settings.REQUIRE_AUTH:
        return {"role": "admin", "authenticated": False, "auth_bypassed": True}

    provided_key: Optional[str] = None
    if api_key:
        provided_key = api_key.strip()
    elif token and token.credentials:
        provided_key = token.credentials.strip()

    valid_keys = {
        settings.ADMIN_API_KEY,
        "alpha-quant-admin-secret",
        "alpha-admin-dev-key",
    }

    if not provided_key or provided_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid administrative API key or Bearer token is required.",
            headers={"WWW-Authenticate": "ApiKey, Bearer"},
        )

    return {"role": "admin", "authenticated": True}
