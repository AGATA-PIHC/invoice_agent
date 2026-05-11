from __future__ import annotations

import pytest

from web.config import MAX_UPLOAD_MB, UPLOAD_DIR


async def test_upload_valid_pdf(client, pdf_bytes):
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert "token" in data
    assert data["filename"] == "invoice.pdf"


async def test_upload_reject_non_pdf(client):
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("doc.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_reject_oversized_file(client):
    big = b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 413


async def test_upload_empty_filename_rejected(client, pdf_bytes):
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("", pdf_bytes, "application/pdf")},
    )
    # FastAPI may return 422 (validation) or 400 (our check) for empty filename
    assert resp.status_code in (400, 422)


async def test_status_endpoint_with_valid_token(client, uploaded_job):
    job_id = uploaded_job["job_id"]
    token = uploaded_job["token"]

    resp = await client.get(f"/api/verify/{job_id}/status?token={token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running", "done", "error")


async def test_result_endpoint_with_valid_token(client, uploaded_job):
    job_id = uploaded_job["job_id"]
    token = uploaded_job["token"]

    resp = await client.get(f"/api/verify/{job_id}/result?token={token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


async def test_unknown_job_returns_404(client, uploaded_job):
    token = uploaded_job["token"]
    fake_id = "00000000-0000-0000-0000-000000000000"
    # Token for fake_id would be different; we need a valid token for this fake_id
    from web.dependencies import make_job_token
    fake_token = make_job_token(fake_id)

    resp = await client.get(f"/api/verify/{fake_id}/status?token={fake_token}")
    assert resp.status_code == 404


async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_file_stored_in_upload_dir(client, pdf_bytes):
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("check.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    dest = UPLOAD_DIR / job_id / "check.pdf"
    assert dest.exists()
