from slowapi import Limiter
from slowapi.util import get_remote_address

# Tests can set this to a unique string per test run to isolate rate limit counters.
_test_key_override: str | None = None


def _resolve_key(request) -> str:
    if _test_key_override is not None:
        return _test_key_override
    return get_remote_address(request)


limiter = Limiter(key_func=_resolve_key)
