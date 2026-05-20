from __future__ import annotations

import asyncio
import logging
import os
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from baca_invoice.agents.document import document_agent
from web.config import APP_NAME, IS_PRODUCTION, JOB_TTL_SECONDS, MAX_CONCURRENT_JOBS
from web.services.agent_io import run_agent_for_json
from web.services.jobs import Job, JobStatus, cleanup_job_file
from web.services.result_validator import validate_agent_result

logger = logging.getLogger(__name__)

_EVICTION_INTERVAL_SECONDS = 300


class AgentRunnerService:
    """Mengelola siklus hidup job ekstraksi dokumen via ADK Runner.

    Job dibuat oleh route handler, dijalankan async dengan batas concurrency,
    lalu di-evict dari memori setelah TTL.
    """

    def __init__(self) -> None:
        _clear_broken_local_proxy()
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            app_name=APP_NAME,
            agent=document_agent,
            session_service=self._session_service,
        )
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    def create_job(self, job_id: str, file_path: str, filename: str) -> None:
        self._jobs[job_id] = Job(job_id=job_id, filename=filename, file_path=file_path)

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    @property
    def active_job_count(self) -> int:
        return sum(
            1
            for job in self._jobs.values()
            if job.status in (JobStatus.PENDING, JobStatus.RUNNING)
        )

    async def run_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        async with self._semaphore:
            job.status = JobStatus.RUNNING
            try:
                job.result = await self._extract_document(job)
                job.status = JobStatus.DONE
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status = JobStatus.ERROR
                job.error = _user_facing_error(exc)
            finally:
                cleanup_job_file(job)

    async def _extract_document(self, job: Job) -> dict:
        user_id = f"user_{job.job_id}"
        session_id = f"session_{job.job_id}"
        await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=f"file_path: {job.file_path}")],
        )
        raw_result = await run_agent_for_json(
            runner=self._runner,
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
        return validate_agent_result(raw_result)

    async def eviction_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_EVICTION_INTERVAL_SECONDS)
                await self._evict_expired_jobs()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Eviction loop error")

    async def _evict_expired_jobs(self) -> None:
        now = time.monotonic()
        async with self._lock:
            expired = [
                job_id
                for job_id, job in self._jobs.items()
                if job.status in (JobStatus.DONE, JobStatus.ERROR)
                and now - job.created_at > JOB_TTL_SECONDS
            ]
        for job_id in expired:
            job = self._jobs.pop(job_id, None)
            logger.info("Evicted job %s", job_id)
            if job:
                cleanup_job_file(job)


def _clear_broken_local_proxy() -> None:
    """Hapus proxy env yang menunjuk ke localhost:9xxx (sering di-set akibat
    misconfig di Windows) supaya google-genai bisa mencapai endpoint Google."""
    broken_markers = ("127.0.0.1:9", "localhost:9", "[::1]:9")
    proxy_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    for key in proxy_keys:
        value = os.environ.get(key, "")
        if any(marker in value for marker in broken_markers):
            os.environ.pop(key, None)


def _user_facing_error(exc: Exception) -> str:
    message = "Terjadi kesalahan saat memproses dokumen."
    if not IS_PRODUCTION:
        return f"{message} Detail: {exc}"
    return message
