from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta


async def _insert_job(trx_id: str, status: str, result=None, error=None, created_at=None):
    """Helper: write a record directly to SQLite for extract tests."""
    import aiosqlite
    from web.db.sqlite import _DB_PATH

    now = (created_at or datetime.now(UTC)).isoformat()
    result_str = __import__("json").dumps(result) if result else None
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO upload_jobs"
            " (trx_id, status, filename, created_at, updated_at, result_json, error_message)"
            " VALUES (?, ?, 'test.pdf', ?, ?, ?, ?)",
            (trx_id, status, now, now, result_str, error),
        )
        await db.commit()


# ── Happy-path extract ────────────────────────────────────────────────────

async def test_extract_progress(client):
    trx_id = str(uuid.uuid4())
    await _insert_job(trx_id, "progress")

    resp = await client.get(f"/api/pinter/extract?trx_id={trx_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "progress"
    assert data["data"] is None
    assert data["trx_id"] == trx_id


async def test_extract_success_returns_data(client):
    trx_id = str(uuid.uuid4())
    result = {"verdict": "AUTENTIK", "total_payment": 1500000.0, "summary": "Test OK"}
    await _insert_job(trx_id, "success", result=result)

    resp = await client.get(f"/api/pinter/extract?trx_id={trx_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"]["verdict"] == "AUTENTIK"
    assert data["data"]["total_payment"] == 1500000.0


async def test_extract_fail_returns_error_message(client):
    trx_id = str(uuid.uuid4())
    await _insert_job(trx_id, "fail", error="Gagal membaca PDF.")

    resp = await client.get(f"/api/pinter/extract?trx_id={trx_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fail"
    assert "Gagal membaca PDF." in data["message"]
    assert data["data"] is None


# ── Error cases ───────────────────────────────────────────────────────────

async def test_extract_unknown_trx_id_returns_404(client):
    resp = await client.get(f"/api/pinter/extract?trx_id={uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "TRX_NOT_FOUND"


async def test_extract_expired_trx_returns_410(client):
    trx_id = str(uuid.uuid4())
    old = datetime.now(UTC) - timedelta(days=8)
    await _insert_job(trx_id, "success", created_at=old)

    resp = await client.get(f"/api/pinter/extract?trx_id={trx_id}")
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "TRX_EXPIRED"


# ── Full upload → extract flow ────────────────────────────────────────────

async def test_upload_then_extract_flow(client, pdf_bytes):
    """Upload a PDF and poll extract until not 'progress' (mock resolves instantly)."""
    up = await client.post(
        "/api/pinter/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert up.status_code == 200
    trx_id = up.json()["trx_id"]

    # Give the background task a moment to complete
    import asyncio
    await asyncio.sleep(0.1)

    ex = await client.get(f"/api/pinter/extract?trx_id={trx_id}")
    assert ex.status_code == 200
    assert ex.json()["status"] in ("progress", "success", "fail")


# ── Validation error format ───────────────────────────────────────────────

async def test_extract_missing_trx_id_returns_400(client):
    """GET tanpa query trx_id → seragam 400 MISSING_TRX_ID."""
    resp = await client.get("/api/pinter/extract")
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "fail"
    assert body["error_code"] == "MISSING_TRX_ID"
    assert "trx_id" in body["message"].lower()
