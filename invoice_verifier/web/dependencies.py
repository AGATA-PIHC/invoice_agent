from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends, HTTPException, Query
from fastapi.requests import Request

from web.config import JOB_SECRET_KEY


def get_runner_service(request: Request):
    return request.app.state.runner_service


def make_job_token(job_id: str) -> str:
    return hmac.new(JOB_SECRET_KEY.encode(), job_id.encode(), hashlib.sha256).hexdigest()


def verify_job_access(
    job_id: str,
    token: str = Query(..., description="Token autentikasi job dari response upload"),
    runner_service=Depends(get_runner_service),
) -> str:
    expected = make_job_token(job_id)
    if not hmac.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail="Token tidak valid.")
    if not runner_service.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
    return job_id
