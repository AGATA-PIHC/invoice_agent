from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from web.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    job_id: str
    filename: str
    file_path: str
    status: JobStatus = JobStatus.PENDING
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.monotonic)


def cleanup_job_file(job: Job) -> None:
    if not job.file_path:
        return
    try:
        job_dir = Path(job.file_path).parent
        if job_dir != UPLOAD_DIR and job_dir.is_relative_to(UPLOAD_DIR):
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception:
        logger.warning("Failed to clean up %s", job.file_path)
