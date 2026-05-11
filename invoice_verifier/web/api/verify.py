from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from web.config import MAX_UPLOAD_MB, UPLOAD_DIR
from web.dependencies import get_runner_service, make_job_token, verify_job_access
from web.models.responses import JobResultResponse, JobStatusResponse, UploadResponse
from web.rate_limit import limiter
from web.services.agent_runner import JobStatus

router = APIRouter(prefix="/api/verify", tags=["verify"])

_MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
_CHUNK = 64 * 1024  # 64 KB read chunks


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    file: UploadFile,
    runner_service=Depends(get_runner_service),
) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diizinkan.")

    safe_name = Path(file.filename).name
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    job_id = str(uuid.uuid4())
    dest_dir = UPLOAD_DIR / job_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name

    if not dest_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    await _stream_to_disk(file, dest_path)

    runner_service.create_job(
        job_id=job_id,
        file_path=str(dest_path.resolve()),
        filename=safe_name,
    )

    import asyncio
    asyncio.create_task(runner_service.run_job(job_id))

    token = make_job_token(job_id)
    return JSONResponse({"job_id": job_id, "filename": safe_name, "token": token})


@router.get("/{job_id}/stream")
async def stream_events(
    request: Request,
    job_id: str = Depends(verify_job_access),
    runner_service=Depends(get_runner_service),
) -> StreamingResponse:
    last_event_id = request.headers.get("Last-Event-ID", "0")
    try:
        start_cursor = int(last_event_id)
    except ValueError:
        start_cursor = 0

    return StreamingResponse(
        runner_service.stream_events(
            job_id,
            start_cursor=start_cursor,
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_result(
    job_id: str = Depends(verify_job_access),
    runner_service=Depends(get_runner_service),
) -> JSONResponse:
    job = runner_service.get_job(job_id)

    if job.status in (JobStatus.RUNNING, JobStatus.PENDING):
        return JSONResponse({"status": job.status, "result": None})

    if job.status == JobStatus.ERROR:
        return JSONResponse({"status": job.status, "error": job.error, "result": None})

    return JSONResponse({"status": job.status, "result": job.result})


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_status(
    job_id: str = Depends(verify_job_access),
    runner_service=Depends(get_runner_service),
) -> JSONResponse:
    job = runner_service.get_job(job_id)
    return JSONResponse({
        "job_id": job_id,
        "status": job.status,
        "filename": job.filename,
        "event_count": len(job.events),
        "error": job.error,
    })


async def _stream_to_disk(file: UploadFile, dest: Path) -> None:
    total = 0
    async with aiofiles.open(dest, "wb") as f:
        while chunk := await file.read(_CHUNK):
            total += len(chunk)
            if total > _MAX_BYTES:
                await f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Ukuran file melebihi {MAX_UPLOAD_MB} MB.",
                )
            await f.write(chunk)
