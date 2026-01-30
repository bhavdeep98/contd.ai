from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader
from typing import Optional

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthContext:
    """Simple auth context for API key authentication."""

    def __init__(self, org_id: str, api_key: Optional[str] = None):
        self.org_id = org_id
        self.api_key = api_key


async def get_auth_context(
    request: Request,
    api_key: Optional[str] = None,
) -> AuthContext:
    """
    Extract auth context from request.

    For SDK usage, expects:
    - X-API-Key header (validated by hosted platform)
    - X-Organization-Id header
    """
    # Get API key from header if not provided
    if api_key is None:
        api_key = request.headers.get("X-API-Key")

    # Get org ID from header
    org_id = request.headers.get("X-Organization-Id")

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if not org_id:
        raise HTTPException(status_code=400, detail="X-Organization-Id header required")

    return AuthContext(org_id=org_id, api_key=api_key)
