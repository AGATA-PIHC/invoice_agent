# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Invoice Verifier is a single-service Python/FastAPI app that verifies Indonesian travel documents (airline tickets, hotel invoices) using Google ADK + Gemini. No database, no Docker required for dev.

### Running the application

```bash
python3 run_web.py --reload
```

Server starts at `http://localhost:8080`. The `--reload` flag enables hot-reloading for development.

**Important:** Use `python3` (not `python`) as `python` is not aliased in this environment.

### Key commands

| Task | Command |
|------|---------|
| Lint | `ruff check invoice_verifier/ tests/ run_web.py` |
| Tests | `pytest tests/ -v` |
| Dev server | `python3 run_web.py --reload` |

### Environment variables

Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` for full LLM functionality. Tests mock the API and do not require a real key.

### Non-obvious notes

- The `PYTHONPATH` must include `invoice_verifier/` for imports to resolve. `run_web.py` handles this via `sys.path.insert`. Tests rely on `pyproject.toml` `[tool.pytest.ini_options] pythonpath = ["invoice_verifier"]`.
- The upload endpoint is `POST /api/verify/upload` (not `/api/verify`).
- All test deps (`pytest`, `pytest-asyncio`, `httpx`, `aiofiles`) are not in `requirements.txt`; they must be installed separately.
- `pip install` goes to `~/.local/bin`; ensure that directory is on `PATH`.
