from __future__ import annotations

import asyncio

import pytest

from web.services.agent_runner import _classify_error


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RuntimeError("429 rate limit exceeded"), ("LLM_RATE_LIMITED", True)),
        (RuntimeError("insufficient_quota"), ("LLM_QUOTA_EXCEEDED", False)),
        (RuntimeError("RESOURCE_EXHAUSTED: quota PerDay exceeded"), ("LLM_QUOTA_EXCEEDED", False)),
        (RuntimeError("402 payment required; credit balance exhausted"), ("LLM_QUOTA_EXCEEDED", False)),
        (RuntimeError("503 service unavailable"), ("LLM_UNAVAILABLE", True)),
        (asyncio.TimeoutError(), ("LLM_TIMEOUT", True)),
        (RuntimeError("context length exceeded"), ("DOCUMENT_TOO_LARGE", False)),
        (RuntimeError("finish_reason=SAFETY"), ("CONTENT_BLOCKED", False)),
        (ValueError("Agent did not return valid JSON"), ("INVALID_LLM_OUTPUT", True)),
        (RuntimeError("PDF is encrypted"), ("UNREADABLE_DOCUMENT", False)),
        (RuntimeError("unexpected failure"), ("INTERNAL_ERROR", False)),
    ],
)
def test_classifies_processing_errors(exc, expected):
    code, _message, retryable = _classify_error(exc)
    assert (code, retryable) == expected


async def test_job_timeout_is_classified(monkeypatch):
    import web.services.agent_runner as module

    monkeypatch.setattr(module, "LLM_TIMEOUT_SECONDS", 0.001)
    service = object.__new__(module.AgentRunnerService)
    service._jobs = {}
    service._semaphore = asyncio.Semaphore(1)
    job = module.Job("job-id", "invoice.pdf", "/tmp/invoice.pdf")  # noqa: S108
    service._jobs[job.job_id] = job

    async def slow_extract(_job):
        await asyncio.sleep(1)
        return {}

    service._extract_document = slow_extract
    await service.run_job(job.job_id)

    assert job.status == module.JobStatus.ERROR
    assert job.error_code == "LLM_TIMEOUT"
    assert job.error is not None
