from __future__ import annotations

import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from web.api.verify import router as verify_router
from web.config import IS_PRODUCTION, UPLOAD_DIR
from web.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from web.models.responses import HealthResponse
from web.rate_limit import limiter
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

    runner_service = AgentRunnerService()
    app.state.runner_service = runner_service
    app.state.limiter = limiter

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
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(verify_router)


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> dict:
    return {
        "status": "ok",
        "jobs_active": app.state.runner_service.active_job_count,
    }


app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
