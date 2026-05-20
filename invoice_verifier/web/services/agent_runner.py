from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from baca_invoice.agents.document import document_agent
from baca_invoice.agents.formatter import formatter_agent
from baca_invoice.models.travel_document import TravelDocumentResult
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from web.config import APP_NAME, IS_PRODUCTION, JOB_TTL_SECONDS, MAX_CONCURRENT_JOBS, UPLOAD_DIR

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


class AgentRunnerService:
    def __init__(self) -> None:
        _clear_broken_local_proxy()
        self._session_service = InMemorySessionService()
        self._document_runner = Runner(
            app_name=APP_NAME,
            agent=document_agent,
            session_service=self._session_service,
        )
        self._formatter_runner = Runner(
            app_name=APP_NAME,
            agent=formatter_agent,
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
                job.result = await self._run_document_agent(job)
                job.status = JobStatus.DONE
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status = JobStatus.ERROR
                job.error = _user_facing_error(exc)
            finally:
                _cleanup_file(job)

    async def _run_document_agent(self, job: Job) -> dict:
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

        result = await _run_agent_for_json(
            runner=self._document_runner,
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
        validated = _validate_agent_result(result)
        return await self._format_with_output_schema(
            validated,
            user_id=user_id,
            session_id=f"{session_id}_formatter",
        )

    async def _format_with_output_schema(
        self,
        result: dict,
        user_id: str,
        session_id: str,
    ) -> dict:
        await self._session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=json.dumps(result, ensure_ascii=False))],
        )
        formatted = await _run_agent_for_json(
            runner=self._formatter_runner,
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
        return _validate_agent_result(formatted)

    async def eviction_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
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
                        _cleanup_file(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Eviction loop error")


async def _run_agent_for_json(
    runner: Runner,
    user_id: str,
    session_id: str,
    message: genai_types.Content,
) -> dict:
    parsed_result: dict | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        structured_result = _extract_set_model_response(event)
        if structured_result is not None:
            parsed_result = structured_result
            continue

        if event.is_final_response() and event.content and event.content.parts:
            raw_text = _extract_text(event.content.parts)
            parsed_result = _unwrap_agent_result(_parse_json_result(raw_text))

    if parsed_result is None:
        raise ValueError("Agent finished without returning a JSON extraction result.")
    return parsed_result


def _validate_agent_result(result: dict) -> dict:
    if not isinstance(result, dict) or set(result) == {"raw"}:
        raise ValueError("Agent did not return a valid JSON object matching the expected schema.")

    doc_type = _normalize_choice(result.get("doc_type"), {"invoice", "receipt", "unknown"})
    sub_type = _normalize_choice(result.get("document_subtype"), {"hotel", "flight", "unknown"})

    if doc_type == "unknown" or _agent_rejects_claimed_doc_type(result, doc_type, sub_type):
        result = _mark_unknown_result(result)
    else:
        result["doc_type"] = doc_type
        result["document_subtype"] = sub_type

    return TravelDocumentResult.model_validate(result).model_dump()


def _normalize_choice(value: Any, allowed: set[str]) -> str:
    normalized = str(value or "unknown").strip().lower()
    return normalized if normalized in allowed else "unknown"


_EMPTY_STRINGS = {"", "-", "-  ", "n/a", "none", "null", "tidak ada", "not available"}
_NON_TRAVEL_DOC_MARKERS = (
    "not an invoice",
    "not a receipt",
    "not invoice",
    "not receipt",
    "not an invoice/receipt",
    "not invoice/receipt",
    "bukan invoice",
    "bukan receipt",
    "bukan faktur",
    "bukan struk",
    "bukan kwitansi",
    "technical guide",
    "panduan",
    "guidance",
)
_INVOICE_EVIDENCE_FIELDS = (
    "invoice_number",
    "issue_date",
    "due_date",
    "vendor_name",
    "vendor_npwp",
    "buyer_name",
    "payment_terms",
    "provider",
    "provider_company",
)
_RECEIPT_EVIDENCE_FIELDS = (
    "receipt_number",
    "transaction_date",
    "payment_date",
    "merchant_name",
    "payer_name",
    "payment_status",
    "provider",
    "provider_company",
)
_HOTEL_EVIDENCE_FIELDS = (
    "order_id",
    "booking_date",
    "hotel_name",
    "check_in_date",
    "check_out_date",
)
_FLIGHT_EVIDENCE_FIELDS = (
    "po_number",
    "transaction_status",
    "traveler_name",
    "airline",
    "route_from",
    "route_to",
    "flight_date",
)


def _agent_rejects_claimed_doc_type(result: dict, doc_type: str, sub_type: str) -> bool:
    if doc_type not in ("invoice", "receipt"):
        return False

    text_parts = [str(result.get("summary") or "")]
    text_parts.extend(str(item) for item in result.get("review_reasons") or [])
    joined_text = " ".join(text_parts).lower()
    if not any(marker in joined_text for marker in _NON_TRAVEL_DOC_MARKERS):
        return False

    evidence_source = (
        _INVOICE_EVIDENCE_FIELDS if doc_type == "invoice" else _RECEIPT_EVIDENCE_FIELDS
    )
    evidence_fields = list(evidence_source)
    if sub_type == "hotel":
        evidence_fields.extend(_HOTEL_EVIDENCE_FIELDS)
    elif sub_type == "flight":
        evidence_fields.extend(_FLIGHT_EVIDENCE_FIELDS)

    has_document_evidence = any(_has_value(result.get(field)) for field in evidence_fields)
    has_amount_evidence = any(
        _has_value(result.get(field))
        for field in ("subtotal", "tax", "service_fee", "total_payment")
    )
    return not has_document_evidence and not has_amount_evidence


def _mark_unknown_result(result: dict) -> dict:
    result = dict(result)
    result["doc_type"] = "unknown"
    result["document_subtype"] = "unknown"
    result["extraction_confidence"] = 0.0
    result["requires_manual_review"] = True

    review_reasons = list(result.get("review_reasons") or [])
    reason = "Dokumen tidak dikenali sebagai invoice atau receipt."
    if reason not in review_reasons:
        review_reasons.insert(0, reason)
    result["review_reasons"] = review_reasons

    if not _has_value(result.get("summary")):
        result["summary"] = "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
    return result


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _EMPTY_STRINGS
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, list):
        return bool(value)
    return bool(value)


def _extract_text(parts) -> str:
    return " ".join(part.text for part in parts if part.text)


def _parse_json_result(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group()

    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def _unwrap_agent_result(data: dict) -> dict:
    if not isinstance(data, dict) or len(data) != 1:
        return data
    key = next(iter(data))
    if key.endswith("_response") and isinstance(data[key], dict):
        return data[key]
    return data


def _extract_set_model_response(event) -> dict | None:
    if not hasattr(event, "get_function_responses"):
        return None
    for response in event.get_function_responses() or []:
        if response.name != "set_model_response":
            continue
        data = response.response
        if isinstance(data, dict) and isinstance(data.get("result"), dict):
            return data["result"]
        if isinstance(data, dict):
            return data
    return None


def _cleanup_file(job: Job) -> None:
    if not job.file_path:
        return
    try:
        job_dir = Path(job.file_path).parent
        if job_dir != UPLOAD_DIR and job_dir.is_relative_to(UPLOAD_DIR):
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception:
        logger.warning("Failed to clean up %s", job.file_path)


def _clear_broken_local_proxy() -> None:
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
