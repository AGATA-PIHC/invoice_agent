from __future__ import annotations

from fastapi import Security
from fastapi.security import APIKeyHeader

from web.config import PINTER_API_KEY
from web.models.v1_upload import V1ApiError

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """FastAPI dependency. No-op jika `PINTER_API_KEY` tidak di-set."""
    if not PINTER_API_KEY:
        return
    if not api_key or api_key != PINTER_API_KEY:
        raise V1ApiError(401, "X-API-Key tidak valid atau tidak ada.", "UNAUTHORIZED")
