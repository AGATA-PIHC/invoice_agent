# Stage 1: build dependencies in an isolated virtual environment.
FROM python:3.12-slim AS builder

WORKDIR /app
RUN python -m venv /venv

COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: lean runtime image.
FROM python:3.12-slim

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app/invoice_verifier" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    UPLOAD_DIR=/app/tmp_uploads

RUN useradd --create-home --system --shell /usr/sbin/nologin appuser

COPY --from=builder /venv /venv

WORKDIR /app
COPY . .

RUN mkdir -p /app/tmp_uploads \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8080"]
