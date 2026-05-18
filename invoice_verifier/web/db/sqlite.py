from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

from web.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)

_DB_PATH = Path(SQLITE_DB_PATH)

_DDL = """
CREATE TABLE IF NOT EXISTS upload_jobs (
    trx_id        TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'progress',
    filename      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    result_json   TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_status ON upload_jobs(status);
"""


async def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.executescript(_DDL)
        await db.commit()
    logger.info("SQLite DB initialized at %s", _DB_PATH)
    await _recover_stale_jobs()


async def _recover_stale_jobs() -> None:
    """Mark jobs that were left in 'progress' from a previous process as failed."""
    now = datetime.now(datetime.UTC).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        result = await db.execute(
            "UPDATE upload_jobs SET status='fail', updated_at=?, error_message=?"
            " WHERE status='progress'",
            (now, "Proses terputus akibat server restart."),
        )
        await db.commit()
        if result.rowcount:
            logger.warning("Recovered %d stale progress job(s) on startup", result.rowcount)


async def create_job(trx_id: str, filename: str) -> None:
    now = datetime.now(datetime.UTC).isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO upload_jobs (trx_id, status, filename, created_at, updated_at)"
            " VALUES (?, 'progress', ?, ?, ?)",
            (trx_id, filename, now, now),
        )
        await db.commit()


async def get_job(trx_id: str) -> dict | None:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT trx_id, status, filename, created_at, updated_at, result_json, error_message"
            " FROM upload_jobs WHERE trx_id = ?",
            (trx_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    record = dict(row)
    if record.get("result_json"):
        try:
            record["result_json"] = json.loads(record["result_json"])
        except (json.JSONDecodeError, TypeError):
            record["result_json"] = None
    return record


async def update_job(
    trx_id: str,
    status: str,
    result_json: dict | None = None,
    error_message: str | None = None,
) -> None:
    now = datetime.now(datetime.UTC).isoformat()
    result_str = json.dumps(result_json) if result_json is not None else None
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "UPDATE upload_jobs SET status=?, updated_at=?, result_json=?, error_message=?"
            " WHERE trx_id=?",
            (status, now, result_str, error_message, trx_id),
        )
        await db.commit()
