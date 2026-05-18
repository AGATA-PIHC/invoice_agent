from __future__ import annotations

from web.config import UPLOAD_DIR


async def test_path_traversal_filename_sanitized(client, pdf_bytes):
    """../../evil.pdf must be saved as evil.pdf inside UPLOAD_DIR, not above it."""
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("../../evil.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    trx_id = resp.json()["trx_id"]

    dest = UPLOAD_DIR / trx_id / "evil.pdf"
    assert dest.exists(), "File should exist inside UPLOAD_DIR"

    parent_evil = UPLOAD_DIR.parent / "evil.pdf"
    assert not parent_evil.exists(), "File must NOT escape UPLOAD_DIR"


async def test_non_pdf_rejected(client):
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_FILE_TYPE"


async def test_null_byte_in_filename(client, pdf_bytes):
    """Filenames with null bytes are sanitized or rejected — must not crash."""
    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("file\x00.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert "\x00" not in resp.json()["trx_id"]


async def test_x_api_key_auth_when_configured(client, pdf_bytes, monkeypatch):
    """When PINTER_API_KEY is set, requests without the header are rejected."""
    import web.api.v1_upload as m
    monkeypatch.setattr(m, "PINTER_API_KEY", "secret-key")

    resp = await client.post(
        "/api/pinter/upload",
        files={"file": ("inv.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/pinter/upload",
        headers={"X-API-Key": "secret-key"},
        files={"file": ("inv.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
