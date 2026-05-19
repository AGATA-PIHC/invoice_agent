from __future__ import annotations

from web.config import MAX_UPLOAD_MB, UPLOAD_DIR

# ── Happy path ────────────────────────────────────────────────────────────

async def test_upload_returns_trx_id(client, pdf_bytes):
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trx_id" in data
    assert data["status"] == "progress"
    assert "message" in data


async def test_upload_file_saved_to_upload_dir(client, pdf_bytes):
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("receipt.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    trx_id = resp.json()["trx_id"]
    dest = UPLOAD_DIR / trx_id / "receipt.pdf"
    assert dest.exists()


async def test_upload_job_created_in_db(client, pdf_bytes):
    from web.db.sqlite import get_job
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    trx_id = resp.json()["trx_id"]
    record = await get_job(trx_id)
    assert record is not None
    # Background task may have completed by now in fast mock — accept either state
    assert record["status"] in ("progress", "success")
    assert record["filename"] == "test.pdf"


# ── Validasi file ─────────────────────────────────────────────────────────

async def test_upload_reject_non_pdf_extension(client):
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("document.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error_code"] == "INVALID_FILE_TYPE"


async def test_upload_reject_fake_pdf_magic_bytes(client):
    """File has .pdf extension but invalid magic bytes."""
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("fake.pdf", b"not a real pdf", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_FILE_TYPE"


async def test_upload_reject_oversized_file(client):
    big = b"%PDF" + b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "FILE_TOO_LARGE"


async def test_upload_reject_missing_file(client):
    """Request without any file field → seragam 400 MISSING_FILE."""
    resp = await client.post("/api/pinter/upload")
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "fail"
    assert body["error_code"] == "MISSING_FILE"
    assert "file" in body["message"].lower() or "pdf" in body["message"].lower()


# ── Doc-type unknown ──────────────────────────────────────────────────────

async def test_upload_unknown_doctype_message(client, pdf_bytes, monkeypatch):
    """When doc_type is unknown the response still returns 200 with doc_type='unknown' message."""
    monkeypatch.setattr("web.api.v1_upload.classify_document", lambda fn, fp: "unknown")

    async def _noop_persist(trx_id, fp):
        pass

    monkeypatch.setattr("web.api.v1_upload._persist_unknown", _noop_persist)
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("unknown.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "progress"
    assert "unknown" in body["message"].lower()


# ── Rate limiting ─────────────────────────────────────────────────────────

async def test_upload_rate_limit_triggers_on_11th_request(client, pdf_bytes):
    """11 uploads from same IP within the window → 429 on the 11th."""
    for i in range(10):
        r = await client.post(
            "/api/pinter/upload",
            files={"file": (f"inv{i}.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200, f"Request {i+1} should succeed"

    r = await client.post(
        "/api/pinter/upload",
        files={"file": ("inv11.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 429
    assert r.json()["error_code"] == "RATE_LIMITED"
