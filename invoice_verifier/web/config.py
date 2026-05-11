import os
import secrets
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / "baca_invoice" / ".env")
load_dotenv(_root / ".env")

APP_ENV: Literal["development", "production"] = os.getenv("APP_ENV", "development")  # type: ignore[assignment]
IS_PRODUCTION: bool = APP_ENV == "production"

UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(_root / "tmp_uploads")))
APP_NAME: str = "invoice_verifier"
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
JOB_TTL_SECONDS: int = int(os.getenv("JOB_TTL_SECONDS", "3600"))
# Auto-generated per process if not set — set JOB_SECRET_KEY in .env for persistence across restarts.
JOB_SECRET_KEY: str = os.getenv("JOB_SECRET_KEY") or secrets.token_hex(32)
