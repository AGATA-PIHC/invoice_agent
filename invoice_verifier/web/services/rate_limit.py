from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request

from web.models.v1_upload import V1ApiError


class SlidingWindowRateLimiter:
    """In-memory sliding-window limiter, di-keyed by client IP.

    Tidak persistent dan tidak shared antar process — cocok untuk single-instance
    deployment. Untuk multi-instance gunakan store eksternal (Redis).
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        recent = [t for t in self._timestamps[key] if now - t < self._window]
        if len(recent) >= self._max:
            self._timestamps[key] = recent
            raise V1ApiError(
                429,
                "Terlalu banyak permintaan. Coba lagi dalam 1 menit.",
                "RATE_LIMITED",
            )
        recent.append(now)
        self._timestamps[key] = recent


_upload_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0)


def enforce_upload_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _upload_limiter.check(ip)
