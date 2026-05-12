from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    token: str


class UnsupportedDocumentError(BaseModel):
    code: str
    message: str
    hint: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    event_count: int
    error: str | None = None


class JobResultResponse(BaseModel):
    status: str
    result: dict | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    jobs_active: int
