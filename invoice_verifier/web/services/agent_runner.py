from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal

from baca_invoice.agents.flight import flight_agent
from baca_invoice.agents.hotel import hotel_agent
from baca_invoice.agents.invoice import invoice_agent
from baca_invoice.agents.receipt import receipt_agent
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
    doc_type: str = "unknown"
    sub_type: str | None = None   # "hotel" | "flight" | None
    status: JobStatus = JobStatus.PENDING
    result: dict | None = None
    error: str | None = None
    events: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    # Replace-and-set: producer swaps the event before setting it, so waiting
    # consumers always wake on a fresh event — no set()+clear() race.
    _notify: asyncio.Event = field(default_factory=asyncio.Event, repr=False, compare=False)

    def push(self, event: dict) -> None:
        self.events.append(event)
        old, self._notify = self._notify, asyncio.Event()
        old.set()

    async def wait_for_events(self, cursor: int, timeout: float = 15.0) -> int:
        if cursor < len(self.events):
            return cursor
        notify = self._notify
        try:
            await asyncio.wait_for(asyncio.shield(notify.wait()), timeout=timeout)
        except TimeoutError:
            pass
        return cursor


_INVOICE_KEYWORDS = frozenset({
    "invoice", "faktur", "tagihan", "ppn", "vat", "npwp",
    "nomor faktur", "jatuh tempo", "due date",
})
_RECEIPT_KEYWORDS = frozenset({
    "receipt", "struk", "bukti bayar", "kwitansi", "e-tiket", "e-ticket",
    "booking confirmation", "payment confirmation", "lunas", "paid",
})
_TRANSPORT_PROVIDERS = frozenset({"airasia", "garuda", "lion_air", "kai"})


def _detect_by_provider(pdf_text: str) -> Literal["invoice", "receipt", "unknown"]:
    """Match KNOWN_PROVIDERS keywords against pdf_text."""
    from baca_invoice.tools.constants import KNOWN_PROVIDERS

    for provider_name, provider_data in KNOWN_PROVIDERS.items():
        for kw in provider_data.get("keywords", []):
            if kw in pdf_text:
                # Transport/airline → receipt (bukti bayar tiket)
                if provider_name in _TRANSPORT_PROVIDERS:
                    return "receipt"
                # Hotel booking platform → invoice (tagihan hotel)
                return "invoice"
    return "unknown"


def classify_document(filename: str, file_path: str) -> Literal["invoice", "receipt", "unknown"]:
    """Classify PDF without any LLM call. Returns 'invoice', 'receipt', or 'unknown'."""
    name = filename.lower()
    inv_score = sum(1 for k in _INVOICE_KEYWORDS if k in name)
    rec_score = sum(1 for k in _RECEIPT_KEYWORDS if k in name)
    pdf_text = ""

    try:
        import fitz
        doc = fitz.open(file_path)
        try:
            if doc.page_count == 0:
                return "unknown"
            pdf_text = doc[0].get_text()[:3000].lower()
        finally:
            doc.close()
    except Exception:
        logger.warning("PDF peek failed for classify_document(%s)", filename)

    inv_score += sum(1 for k in _INVOICE_KEYWORDS if k in pdf_text)
    rec_score += sum(1 for k in _RECEIPT_KEYWORDS if k in pdf_text)

    if inv_score == 0 and rec_score == 0:
        return _detect_by_provider(pdf_text) if pdf_text else "unknown"

    if inv_score != rec_score:
        return "invoice" if inv_score > rec_score else "receipt"

    if pdf_text:
        provider_type = _detect_by_provider(pdf_text)
        if provider_type != "unknown":
            return provider_type

    return "unknown"


_HOTEL_KEYWORDS = frozenset({
    "hotel", "penginapan", "kamar", "check-in", "checkin", "checkout",
    "inn", "resort", "malam", "nights", "room",
})
_FLIGHT_KEYWORDS = frozenset({
    "pesawat", "flight", "airasia", "garuda", "lion",
    "airline", "boarding", "citilink", "batik", "wings",
})


def classify_sub_type(filename: str, file_path: str) -> str | None:
    """Classifier 2 (independen): cek apakah dokumen hotel atau flight.
    Returns 'hotel', 'flight', atau None jika tidak terdeteksi."""
    name = filename.lower()
    h_score = sum(1 for k in _HOTEL_KEYWORDS if k in name)
    f_score = sum(1 for k in _FLIGHT_KEYWORDS if k in name)
    pdf_text = ""

    try:
        import fitz
        doc = fitz.open(file_path)
        try:
            if doc.page_count > 0:
                pdf_text = doc[0].get_text()[:3000].lower()
        finally:
            doc.close()
    except Exception:
        logger.warning("PDF peek failed for classify_sub_type(%s)", filename)

    h_score += sum(1 for k in _HOTEL_KEYWORDS if k in pdf_text)
    f_score += sum(1 for k in _FLIGHT_KEYWORDS if k in pdf_text)

    if h_score == 0 and f_score == 0:
        return None
    if h_score >= f_score:
        return "hotel"
    return "flight"


_DOC_TYPE_LABEL = {"invoice": "Invoice", "receipt": "Receipt", "unknown": "Dokumen"}


def _clear_broken_local_proxy() -> None:
    """Ignore proxy env vars commonly set by sandboxes to an unavailable discard port."""
    broken_markers = ("127.0.0.1:9", "localhost:9", "[::1]:9")
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        value = os.environ.get(key, "")
        if any(marker in value for marker in broken_markers):
            os.environ.pop(key, None)


class AgentRunnerService:
    def __init__(self) -> None:
        _clear_broken_local_proxy()
        self._session_service = InMemorySessionService()
        self._invoice_runner = Runner(
            app_name=APP_NAME,
            agent=invoice_agent,
            session_service=self._session_service,
        )
        self._receipt_runner = Runner(
            app_name=APP_NAME,
            agent=receipt_agent,
            session_service=self._session_service,
        )
        self._hotel_runner = Runner(
            app_name=APP_NAME,
            agent=hotel_agent,
            session_service=self._session_service,
        )
        self._flight_runner = Runner(
            app_name=APP_NAME,
            agent=flight_agent,
            session_service=self._session_service,
        )
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    def create_job(
        self,
        job_id: str,
        file_path: str,
        filename: str,
        doc_type: str = "unknown",
        sub_type: str | None = None,
    ) -> None:
        self._jobs[job_id] = Job(
            job_id=job_id,
            filename=filename,
            file_path=file_path,
            doc_type=doc_type,
            sub_type=sub_type,
        )

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    @property
    def active_job_count(self) -> int:
        return sum(
            1 for j in self._jobs.values()
            if j.status in (JobStatus.PENDING, JobStatus.RUNNING)
        )

    async def run_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        async with self._semaphore:
            job.status = JobStatus.RUNNING
            user_id = f"user_{job_id}"
            session_id = f"session_{job_id}"

            # Routing berdasarkan 2-stage classification (doc_type + sub_type).
            # Sub-type must stay compatible with the public doc_type.  For example,
            # "tiket.com" is a travel provider but not always a flight document.
            doc_type = job.doc_type
            sub_type = job.sub_type
            effective_sub_type = None
            if doc_type == "invoice" and sub_type == "hotel":
                runner = self._hotel_runner
                effective_sub_type = sub_type
            elif doc_type == "receipt" and sub_type == "flight":
                runner = self._flight_runner
                effective_sub_type = sub_type
            elif doc_type == "invoice":
                runner = self._invoice_runner
            else:
                runner = self._receipt_runner
            label = _DOC_TYPE_LABEL.get(doc_type, "Dokumen")
            if effective_sub_type:
                label = f"{label} ({effective_sub_type})"

            try:
                await self._session_service.create_session(
                    app_name=APP_NAME,
                    user_id=user_id,
                    session_id=session_id,
                )

                message = genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=f"file_path: {job.file_path}")],
                )

                job.push({
                    "type": "status",
                    "message": f"Terdeteksi: {label}. Memulai verifikasi...",
                })

                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=message,
                ):
                    for mapped in _map_event(event):
                        job.push(mapped)

                    if event.is_final_response() and event.content and event.content.parts:
                        raw_text = _extract_text(event.content.parts)
                        parsed = _parse_json_result(raw_text)
                        result = _unwrap_agent_result(parsed)
                        # Pastikan doc_type stage-1 selalu ada di output
                        if isinstance(result, dict):
                            result.setdefault("doc_type", job.doc_type)
                        job.result = result

                job.status = JobStatus.DONE
                job.push({"type": "complete", "result": job.result})

            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status = JobStatus.ERROR
                message = "Terjadi kesalahan saat memproses dokumen."
                if not IS_PRODUCTION:
                    message = f"{message} Detail: {exc}"
                job.error = message
                job.push({"type": "error", "message": message})

            finally:
                _cleanup_file(job)

    async def stream_events(
        self,
        job_id: str,
        start_cursor: int = 0,
        is_disconnected=None,
        max_duration: float = 600.0,
    ) -> AsyncGenerator[str, None]:
        """Yield SSE frames. is_disconnected is an optional async callable () -> bool."""
        job = self._jobs.get(job_id)
        if not job:
            yield _sse({"type": "error", "message": "Job tidak ditemukan"})
            return

        cursor = start_cursor
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max_duration

        while True:
            if loop.time() >= deadline:
                break

            while cursor < len(job.events):
                yield _sse_with_id(job.events[cursor], cursor)
                cursor += 1

            if job.status in (JobStatus.DONE, JobStatus.ERROR):
                break

            if is_disconnected and await is_disconnected():
                break

            notify = job._notify
            try:
                await asyncio.wait_for(asyncio.shield(notify.wait()), timeout=15.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                # Refresh notify reference in case push() replaced it while we waited
                if cursor < len(job.events):
                    continue

    async def eviction_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)  # check every 5 minutes
                now = time.monotonic()
                async with self._lock:
                    expired = [
                        jid for jid, j in self._jobs.items()
                        if j.status in (JobStatus.DONE, JobStatus.ERROR)
                        and now - j.created_at > JOB_TTL_SECONDS
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


def _cleanup_file(job: Job) -> None:
    if not job.file_path:
        return
    try:
        job_dir = Path(job.file_path).parent
        if job_dir != UPLOAD_DIR and job_dir.is_relative_to(UPLOAD_DIR):
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception:
        logger.warning("Failed to clean up %s", job.file_path)


def _map_event(event) -> list[dict]:
    author: str = event.author or "unknown"

    if not event.content or not event.content.parts:
        return []

    results: list[dict] = []
    for part in event.content.parts:
        function_call = getattr(part, "function_call", None)
        function_response = getattr(part, "function_response", None)
        text = getattr(part, "text", None)

        if function_call:
            results.append({
                "type": "agent_event",
                "author": author,
                "kind": "tool_call",
                "tool": function_call.name,
            })
            results.append({
                "type": "thinking",
                "stage": "tool_call",
                "status": "running",
                "message": f"Menjalankan tool {function_call.name}.",
                "details": {"tool": function_call.name, "author": author},
            })
        elif function_response:
            resp = function_response.response or {}
            if not isinstance(resp, dict):
                resp = {"raw": str(resp), "success": True}
            results.append({
                "type": "agent_event",
                "author": author,
                "kind": "tool_result",
                "tool": function_response.name,
                "success": bool(resp.get("success", True)),
            })
            details = _tool_response_details(resp)
            results.append({
                "type": "thinking",
                "stage": "tool_result",
                "status": "done" if bool(resp.get("success", True)) else "error",
                "message": _tool_response_message(function_response.name, resp),
                "details": {**details, "tool": function_response.name, "author": author},
            })
        elif text and text.strip():
            results.append({
                "type": "agent_event",
                "author": author,
                "kind": "text",
                "text": text[:300],
            })
    return results


def _tool_response_details(resp: dict) -> dict:
    auth = resp.get("authenticity") if isinstance(resp, dict) else None
    details = {
        "success": bool(resp.get("success", True)) if isinstance(resp, dict) else True,
    }
    if isinstance(resp, dict):
        if "total_pages" in resp:
            details["pages"] = resp.get("total_pages")
        if isinstance(auth, dict):
            details["provider"] = auth.get("detected_provider")
            details["verdict"] = auth.get("verdict")
            details["confidence_score"] = auth.get("confidence_score")
            details["warning_flags"] = auth.get("warning_flags") or []
    return details


def _tool_response_message(tool_name: str, resp: dict) -> str:
    if not isinstance(resp, dict) or not resp.get("success", True):
        return f"Tool {tool_name} gagal membaca dokumen."
    auth = resp.get("authenticity") if isinstance(resp.get("authenticity"), dict) else {}
    pages = resp.get("total_pages", 0)
    verdict = auth.get("verdict") or "belum diketahui"
    provider = auth.get("detected_provider") or "-"
    return f"PDF terbaca ({pages} halaman). Provider: {provider}. Verdict: {verdict}."


def _extract_text(parts) -> str:
    return " ".join(p.text for p in parts if p.text)


def _parse_json_result(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group()
    # Normalize Python literal booleans/None to valid JSON before parsing.
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)
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


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_with_id(data: dict, event_id: int) -> str:
    return f"id: {event_id}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
