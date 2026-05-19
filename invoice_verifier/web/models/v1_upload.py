from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    trx_id: str
    status: str
    message: str


class ExtractResponse(BaseModel):
    trx_id: str
    status: str
    message: str
    data: dict | None = None


class V1ErrorResponse(BaseModel):
    status: str = "fail"
    message: str
    error_code: str


class V1ApiError(Exception):
    def __init__(self, status_code: int, message: str, error_code: str) -> None:
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
