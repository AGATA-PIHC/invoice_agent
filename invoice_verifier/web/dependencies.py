from __future__ import annotations

from fastapi.requests import Request


def get_runner_service(request: Request):
    return request.app.state.runner_service
