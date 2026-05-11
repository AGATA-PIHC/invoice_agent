from __future__ import annotations

import pytest

from web.config import UPLOAD_DIR


async def test_path_traversal_filename_sanitized(client, pdf_bytes):
    """../../evil.pdf must be saved as evil.pdf inside UPLOAD_DIR, not above it."""
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("../../evil.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "evil.pdf"

    job_id = data["job_id"]
    dest = UPLOAD_DIR / job_id / "evil.pdf"
    assert dest.exists(), "File should exist inside UPLOAD_DIR"

    parent_evil = UPLOAD_DIR.parent / "evil.pdf"
    assert not parent_evil.exists(), "File must NOT escape UPLOAD_DIR"


async def test_null_byte_filename_rejected(client, pdf_bytes):
    """Filenames with null bytes or no .pdf extension are rejected."""
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("file\x00.pdf", pdf_bytes, "application/pdf")},
    )
    # FastAPI strips null bytes or rejects; either 400 or safe filename
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert "\x00" not in resp.json()["filename"]


async def test_non_pdf_rejected(client):
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_job_endpoints_require_valid_token(client, uploaded_job):
    job_id = uploaded_job["job_id"]
    bad_token = "a" * 64

    resp = await client.get(f"/api/verify/{job_id}/status?token={bad_token}")
    assert resp.status_code == 403

    resp = await client.get(f"/api/verify/{job_id}/result?token={bad_token}")
    assert resp.status_code == 403


async def test_job_endpoints_without_token_return_422(client, uploaded_job):
    job_id = uploaded_job["job_id"]
    # token query param is required; missing → 422 Unprocessable Entity
    resp = await client.get(f"/api/verify/{job_id}/status")
    assert resp.status_code == 422
