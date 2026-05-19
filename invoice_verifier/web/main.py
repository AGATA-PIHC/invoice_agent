from __future__ import annotations

import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from web.api.v1_upload import router as v1_upload_router
from web.config import ENABLE_DOCS, UPLOAD_DIR
from web.db.sqlite import init_db
from web.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from web.models.responses import HealthResponse
from web.models.v1_upload import V1ApiError, V1ErrorResponse
from web.services.agent_runner import AgentRunnerService

_STATIC_DIR = Path(__file__).parent / "static"

_LOG_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "fmt": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","msg":"%(message)s"}'
            ),
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.config.dictConfig(_LOG_CONFIG)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()

    runner_service = AgentRunnerService()
    app.state.runner_service = runner_service
    eviction_task = asyncio.create_task(runner_service.eviction_loop())
    try:
        yield
    finally:
        eviction_task.cancel()
        with suppress(asyncio.CancelledError):
            await eviction_task


app = FastAPI(
    title="Invoice Verifier",
    description="Verifikasi dokumen perjalanan dinas menggunakan AI Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
    redoc_url=None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(V1ApiError)
async def v1_api_error_handler(request, exc: V1ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=V1ErrorResponse(message=exc.message, error_code=exc.error_code).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """Konversi 422 default FastAPI menjadi format seragam { status, message, error_code }."""
    errors = exc.errors()
    loc_paths = [tuple(e.get("loc", ())) for e in errors]

    if ("body", "file") in loc_paths:
        message, code = "File PDF wajib diisi.", "MISSING_FILE"
    elif ("query", "trx_id") in loc_paths:
        message, code = "Parameter trx_id wajib diisi.", "MISSING_TRX_ID"
    else:
        message = errors[0].get("msg") if errors else "Permintaan tidak valid."
        code = "VALIDATION_ERROR"

    return JSONResponse(
        status_code=400,
        content=V1ErrorResponse(message=message, error_code=code).model_dump(),
    )


app.include_router(v1_upload_router)


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> dict:
    return {
        "status": "ok",
        "jobs_active": app.state.runner_service.active_job_count,
    }


app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
