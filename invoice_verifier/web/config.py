import os
import secrets
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# web/config.py → invoice_verifier/web/ → invoice_verifier/ → project root
_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")

APP_ENV: Literal["development", "production"] = os.getenv("APP_ENV", "development")  # type: ignore[assignment]
IS_PRODUCTION: bool = APP_ENV == "production"

UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(_root / "tmp_uploads")))
APP_NAME: str = "invoice_verifier"
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
JOB_TTL_SECONDS: int = int(os.getenv("JOB_TTL_SECONDS", "3600"))
# Auto-generated per process if not set — set JOB_SECRET_KEY in .env to persist across restarts.
JOB_SECRET_KEY: str = os.getenv("JOB_SECRET_KEY") or secrets.token_hex(32)

# API key for machine-to-machine travel integration (PISmart → PINTER).
# If unset, auth is disabled (development only).
TRAVEL_API_KEY: str | None = os.getenv("TRAVEL_API_KEY") or None

# SQLite database path for PINTER upload/extract API.
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", str(_root / "data" / "invoice_verifier.db"))

# API key for PINTER endpoints (X-API-Key header). Unset = auth disabled (dev only).
PINTER_API_KEY: str | None = os.getenv("PINTER_API_KEY") or None

# Time-to-live for trx_id in PINTER endpoints. After this, GET /extract returns TRX_EXPIRED.
PINTER_TRX_TTL_DAYS: int = int(os.getenv("PINTER_TRX_TTL_DAYS", "7"))
