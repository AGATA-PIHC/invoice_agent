# ── Stage 1: build dependencies in isolated venv ───────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
RUN python -m venv /venv
COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Stage 2: lean runtime image ────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user
RUN useradd -r -s /bin/false appuser

COPY --from=builder /venv /venv
WORKDIR /app
COPY . .

RUN mkdir -p tmp_uploads && chown -R appuser:appuser /app

# Set env before switching user so PATH is available to healthcheck & CMD
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/invoice_verifier"

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# run_web.py binds to 127.0.0.1 (loopback only) which is unreachable from outside
# the container. Use uvicorn directly with 0.0.0.0 so Docker can forward the port.
# PYTHONPATH above makes `web.main` importable from /app/invoice_verifier/.
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8080"]
