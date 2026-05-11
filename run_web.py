"""Entry point: jalankan `python run_web.py` untuk memulai server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "invoice_verifier"))
import uvicorn

if __name__ == "__main__":
    reload = "--reload" in sys.argv
    print("Starting Invoice Verifier at http://localhost:8080")
    uvicorn.run("web.main:app", host="127.0.0.1", port=8080, reload=reload)
