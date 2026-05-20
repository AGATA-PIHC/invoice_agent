from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile
from fastapi import File as FastAPIFile

from web.config import MAX_UPLOAD_MB, PINTER_TRX_TTL_DAYS, UPLOAD_DIR
from web.db.sqlite import create_job, get_job, update_job
from web.dependencies import get_runner_service
from web.models.v1_upload import ExtractResponse, UploadResponse, V1ApiError
from web.security import verify_api_key
from web.services.jobs import JobStatus
from web.services.rate_limit import enforce_upload_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pinter", tags=["pinter"])

_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
_background_tasks: set[asyncio.Task] = set()


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
    file: UploadFile = FastAPIFile(...),
    runner_service=Depends(get_runner_service),
    _auth: None = Depends(verify_api_key),
    _ratelimit: None = Depends(enforce_upload_rate_limit),
) -> UploadResponse:
    pdf_bytes = await _read_validated_pdf(file)

    trx_id = str(uuid.uuid4())
    filename = Path(file.filename or "").name
    dest_path = _persist_upload(trx_id, filename, pdf_bytes)

    try:
        await create_job(trx_id, filename)
    except Exception as e:
        shutil.rmtree(dest_path.parent, ignore_errors=True)
        logger.error("Gagal simpan job ke DB untuk trx %s: %s", trx_id, e)
        raise V1ApiError(
            500, "Terjadi kesalahan internal. Silakan coba lagi.", "INTERNAL_ERROR"
        ) from e

    logger.info("trx %s: dokumen diterima, memulai document_agent", trx_id)

    runner_service.create_job(
        job_id=trx_id,
        file_path=str(dest_path.resolve()),
        filename=filename,
    )
    _schedule_background(_run_and_persist(trx_id, runner_service))

    return UploadResponse(
        trx_id=trx_id,
        status="progress",
        message="Dokumen diterima dan sedang diproses.",
    )


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
    _auth: None = Depends(verify_api_key),
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

    return _build_extract_response(trx_id, record)


async def _read_validated_pdf(file: UploadFile) -> bytes:
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
    return pdf_bytes


def _persist_upload(trx_id: str, filename: str, pdf_bytes: bytes) -> Path:
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
    return dest_path


def _schedule_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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


def _build_extract_response(trx_id: str, record: dict) -> ExtractResponse:
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
    return datetime.now(UTC) - created > timedelta(days=PINTER_TRX_TTL_DAYS)
