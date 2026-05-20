from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Security, UploadFile
from fastapi import File as FastAPIFile
from fastapi.security import APIKeyHeader

from web.config import MAX_UPLOAD_MB, PINTER_API_KEY, PINTER_TRX_TTL_DAYS, UPLOAD_DIR
from web.db.sqlite import create_job, get_job, update_job
from web.dependencies import get_runner_service
from web.models.v1_upload import ExtractResponse, UploadResponse, V1ApiError
from web.services.agent_runner import JobStatus, classify_document, classify_sub_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pinter", tags=["pinter"])

_background_tasks: set[asyncio.Task] = set()

# Simple sliding-window rate limiter: max 10 upload requests per IP per minute.
_RATE_LIMIT = 10
_RATE_WINDOW = 60.0
_ip_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    timestamps = _ip_timestamps[ip]
    _ip_timestamps[ip] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_ip_timestamps[ip]) >= _RATE_LIMIT:
        raise V1ApiError(429, "Terlalu banyak permintaan. Coba lagi dalam 1 menit.", "RATE_LIMITED")
    _ip_timestamps[ip].append(now)

_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not PINTER_API_KEY:
        return
    if not api_key or api_key != PINTER_API_KEY:
        raise V1ApiError(401, "X-API-Key tidak valid atau tidak ada.", "UNAUTHORIZED")


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload PDF invoice untuk diekstraksi",
    description=(
        "PISmart mengirim file PDF via multipart/form-data. "
        "Response langsung mengembalikan trx_id — proses ekstraksi berjalan di background. "
        "Gunakan GET /api/pinter/extract?trx_id={trx_id} untuk mengambil hasil."
    ),
)
async def upload_document(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    runner_service=Depends(get_runner_service),
    _: None = Depends(_verify_api_key),
) -> UploadResponse:
    _check_rate_limit(request)
    if not file.filename:
        raise V1ApiError(400, "Field 'file' wajib diisi.", "MISSING_FILE")

    if not file.filename.lower().endswith(".pdf"):
        raise V1ApiError(400, "File harus berformat PDF.", "INVALID_FILE_TYPE")

    pdf_bytes = await file.read()

    if len(pdf_bytes) > _MAX_BYTES:
        raise V1ApiError(
            413,
            f"Ukuran file melebihi batas maksimum {MAX_UPLOAD_MB} MB.",
            "FILE_TOO_LARGE",
        )

    if len(pdf_bytes) < 5 or pdf_bytes[:4] != b"%PDF":
        raise V1ApiError(400, "File harus berformat PDF.", "INVALID_FILE_TYPE")

    trx_id = str(uuid.uuid4())
    filename = Path(file.filename).name
    dest_dir = UPLOAD_DIR / trx_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    if not dest_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise V1ApiError(400, "Nama file tidak valid.", "INVALID_FILE_TYPE")

    try:
        dest_path.write_bytes(pdf_bytes)
    except OSError as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.error("Gagal tulis file untuk trx %s: %s", trx_id, e)
        raise V1ApiError(
            500, "Terjadi kesalahan internal. Silakan coba lagi.", "INTERNAL_ERROR"
        ) from e

    resolved_path = str(dest_path.resolve())
    doc_type = classify_document(filename, resolved_path)

    try:
        await create_job(trx_id, filename)
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        logger.error("Gagal simpan job ke DB untuk trx %s: %s", trx_id, e)
        raise V1ApiError(
            500, "Terjadi kesalahan internal. Silakan coba lagi.", "INTERNAL_ERROR"
        ) from e

    if doc_type == "unknown":
        logger.info("trx %s: doc_type unknown — skip AI, kembalikan TravelDocumentResult", trx_id)
        task = asyncio.create_task(_persist_unknown(trx_id, resolved_path))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return UploadResponse(
            trx_id=trx_id,
            status="progress",
            message=(
                "Dokumen diterima. Tidak dikenali sebagai invoice/receipt — "
                "akan dikembalikan dengan doc_type='unknown'."
            ),
        )

    # Classifier 2 (independen): hotel / flight / None
    sub_type = classify_sub_type(filename, resolved_path)
    logger.info("trx %s: doc_type=%s sub_type=%s", trx_id, doc_type, sub_type)

    runner_service.create_job(
        job_id=trx_id,
        file_path=resolved_path,
        filename=filename,
        doc_type=doc_type,
        sub_type=sub_type,
    )

    task = asyncio.create_task(_run_and_persist(trx_id, runner_service))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return UploadResponse(
        trx_id=trx_id,
        status="progress",
        message="Dokumen diterima dan sedang diproses.",
    )


async def _run_and_persist(trx_id: str, runner_service) -> None:
    try:
        await runner_service.run_job(trx_id)
        job = runner_service.get_job(trx_id)
        if job and job.status == JobStatus.DONE:
            await update_job(trx_id, status="success", result_json=job.result)
        else:
            error_msg = (job.error if job else None) or "Verifikasi gagal."
            await update_job(trx_id, status="fail", error_message=error_msg)
    except Exception as exc:
        logger.exception("run_and_persist gagal untuk trx %s", trx_id)
        await update_job(trx_id, status="fail", error_message=str(exc))


async def _persist_unknown(trx_id: str, file_path: str) -> None:
    try:
        from baca_invoice.models.authenticity import DocumentAuthenticity
        from baca_invoice.models.travel_document import TravelDocumentResult
        from baca_invoice.tools.authenticity import analyze_document_authenticity

        raw_auth = analyze_document_authenticity(file_path)
        raw_auth["verdict"] = "PALSU/DIEDIT"
        raw_auth["is_suspicious"] = True
        raw_auth["confidence_score"] = 0.0
        warning_flags = list(raw_auth.get("warning_flags") or [])
        if "unknown_doc_type" not in warning_flags:
            warning_flags.insert(0, "unknown_doc_type")
        raw_auth["warning_flags"] = warning_flags

        fake_evidence = list(raw_auth.get("fake_evidence") or [])
        fake_evidence.insert(
            0,
            "[BUKTI - DOKUMEN TIDAK TERKLASIFIKASI] "
            "Dokumen tidak dikenali sebagai invoice atau receipt, sehingga tidak dapat "
            "divalidasi sebagai dokumen perjalanan dinas yang autentik.",
        )
        raw_auth["fake_evidence"] = fake_evidence
        raw_auth["analysis_notes"] = (
            "Dokumen tidak dikenali sebagai invoice atau receipt. "
            "Status authenticity dipaksa tidak autentik untuk kebutuhan verifikasi."
        )

        result = TravelDocumentResult(
            doc_type="unknown",
            document_subtype="unknown",
            authenticity=DocumentAuthenticity(**raw_auth),
            extraction_confidence=0.0,
            requires_manual_review=True,
            review_reasons=["Dokumen tidak dikenali sebagai invoice atau receipt."],
            summary="Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi.",
        )
        await update_job(trx_id, status="success", result_json=result.model_dump())
    except Exception as exc:
        logger.exception("persist_unknown gagal untuk trx %s", trx_id)
        await update_job(trx_id, status="fail", error_message=str(exc))


@router.get(
    "/extract",
    response_model=ExtractResponse,
    summary="Ambil hasil ekstraksi berdasarkan trx_id (query param)",
    description=(
        "Poll endpoint ini setelah POST /upload. "
        "status='progress' artinya masih berjalan. "
        "status='success' artinya data hasil ekstraksi tersedia di field 'data'. "
        "status='fail' artinya ekstraksi gagal. "
        f"trx_id kedaluwarsa setelah {PINTER_TRX_TTL_DAYS} hari (error TRX_EXPIRED)."
    ),
)
async def get_extract(
    trx_id: str,
    _: None = Depends(_verify_api_key),
) -> ExtractResponse:
    try:
        record = await get_job(trx_id)
    except Exception as e:
        logger.error("Gagal baca DB untuk trx %s: %s", trx_id, e)
        raise V1ApiError(500, "Terjadi kesalahan internal.", "INTERNAL_ERROR") from e

    if record is None:
        raise V1ApiError(404, "Transaction ID tidak ditemukan.", "TRX_NOT_FOUND")

    if _is_expired(record.get("created_at")):
        raise V1ApiError(410, "Transaction ID sudah kedaluwarsa.", "TRX_EXPIRED")

    status = record["status"]

    if status == "progress":
        return ExtractResponse(
            trx_id=trx_id,
            status="progress",
            message="Dokumen sedang diproses.",
            data=None,
        )

    if status == "fail":
        return ExtractResponse(
            trx_id=trx_id,
            status="fail",
            message=record.get("error_message") or "Ekstraksi gagal.",
            data=None,
        )

    result_json = record.get("result_json")
    if result_json is None:
        return ExtractResponse(
            trx_id=trx_id,
            status="fail",
            message="Ekstraksi selesai tanpa hasil valid. Silakan upload ulang dokumen.",
            data=None,
        )

    return ExtractResponse(
        trx_id=trx_id,
        status="success",
        message="Ekstraksi berhasil.",
        data=result_json,
    )


def _is_expired(created_at: str | None) -> bool:
    if not created_at:
        return False
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age = datetime.now(UTC) - created
    return age > timedelta(days=PINTER_TRX_TTL_DAYS)
