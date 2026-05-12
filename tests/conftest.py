from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def isolate_rate_limit():
    """Give each test a unique rate-limit key so tests don't share counters."""
    import web.rate_limit as rl
    rl._test_key_override = str(uuid.uuid4())
    yield
    rl._test_key_override = None


@pytest.fixture(autouse=True)
def stub_run_job(monkeypatch):
    # Background task would call Gemini (no API key in CI) and its finally
    # block deletes the upload dir, racing with assertions on the file.
    async def _noop(self, job_id: str) -> None:
        return

    from web.services.agent_runner import AgentRunnerService
    monkeypatch.setattr(AgentRunnerService, "run_job", _noop)


@pytest.fixture(autouse=True)
def stub_classify_document(monkeypatch):
    # Minimal test PDFs have no travel keywords, so classify_document always
    # returns "unknown" and the upload endpoint rejects them with 422.
    from web.api import verify
    monkeypatch.setattr(verify, "classify_document", lambda filename, file_path: "flight")


@pytest.fixture
async def client():
    """Async test client that starts the full app lifespan."""
    from web.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        async with app.router.lifespan_context(app):
            yield c


@pytest.fixture
def pdf_bytes() -> bytes:
    return b"%PDF-1.4 1 0 obj << /Type /Catalog >> endobj"


@pytest.fixture
async def uploaded_job(client, pdf_bytes):
    """Upload a minimal PDF and return {job_id, token, filename}."""
    resp = await client.post(
        "/api/verify/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    return resp.json()
