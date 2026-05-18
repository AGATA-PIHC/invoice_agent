# Invoice Verifier — PINTER

Layanan verifikasi dokumen perjalanan dinas (invoice & receipt) menggunakan AI Agent berbasis Google Gemini.
Mendukung integrasi mesin-ke-mesin dengan sistem eksternal (PISmart).

---

## Fitur Utama

| Endpoint | Deskripsi |
|----------|-----------|
| `POST /api/verify/upload` | Upload PDF → terima `job_id` + token |
| `GET /api/verify/{job_id}/stream` | Stream hasil verifikasi via SSE |
| `GET /api/verify/{job_id}/status` | Poll status verifikasi |
| `GET /api/verify/{job_id}/result` | Ambil hasil akhir verifikasi |
| `POST /api/travel/submit` | Integrasi PISmart: kirim dokumen PDF (base64) |
| `GET /api/travel/result/{transaction_id}` | Integrasi PISmart: poll hasil verifikasi |
| `POST /api/pinter/upload` | Upload PDF invoice → terima `trx_id`, simpan ke SQLite |
| `GET /api/pinter/extract?trx_id={trx_id}` | Poll hasil ekstraksi dari SQLite |
| `GET /health` | Liveness check |

Dokumentasi lengkap: [`web/API.md`](web/API.md)

---

## Arsitektur

```
                    ┌─────────────┐
                    │  FastAPI    │
                    │  (web/)     │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   /api/verify/    /api/travel/    /api/pinter/
   (SSE stream)    (base64 JSON)   (multipart PDF)
          │                │                │
          └────────────────┼────────────────┘
                           │
                  AgentRunnerService
                  (background job)
                           │
                  ┌────────┴────────┐
                  │  Google Gemini  │
                  │  AI Agents      │
                  └────────┬────────┘
                           │
                    hasil ekstraksi
                           │
              ┌────────────┴──────────┐
              │                       │
         in-memory              SQLite DB
      (_travel_meta)          (upload_jobs)
     [/api/travel/]          [/api/pinter/]
```

---

## Persyaratan

- Python 3.11+
- Google AI Studio API key (atau Vertex AI)
- `uv` atau `pip` untuk manajemen paket

---

## Konfigurasi

Salin `.env_example` ke `.env` dan isi nilai yang diperlukan:

```sh
cp baca_invoice/.env_example baca_invoice/.env
```

| Variabel | Keterangan | Default |
|----------|------------|---------|
| `GOOGLE_API_KEY` | API key Google AI Studio | — (wajib) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` untuk Vertex AI, `0` untuk AI Studio | `0` |
| `TRAVEL_API_KEY` | API key untuk endpoint `/api/travel/` | — (opsional, nonaktif jika tidak diset) |
| `PINTER_API_KEY` | API key untuk endpoint `/api/pinter/` (header `X-API-Key`) | — (opsional, nonaktif jika tidak diset) |
| `PINTER_TRX_TTL_DAYS` | TTL trx_id dalam hari (setelah lewat → `TRX_EXPIRED`) | `7` |
| `SQLITE_DB_PATH` | Path file SQLite untuk endpoint `/api/pinter/` | `data/invoice_verifier.db` |
| `JOB_SECRET_KEY` | Secret untuk HMAC token job (persist antar restart) | auto-generate |

---

## Instalasi & Menjalankan

```sh
# Install dependensi
pip install -r requirements.txt

# Jalankan server
cd web
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Atau dengan Docker:

```sh
docker build -t invoice-verifier .
docker run -p 8080:8080 --env-file baca_invoice/.env invoice-verifier
```

---

## Panduan Penggunaan API

### Upload & Verifikasi (SSE)

```sh
# 1. Upload PDF
curl -X POST http://localhost:8080/api/verify/upload \
  -F "file=@invoice.pdf"
# → { "job_id": "...", "token": "..." }

# 2. Stream hasil
curl "http://localhost:8080/api/verify/{job_id}/stream?token={token}"
```

### Integrasi PISmart — Travel API

```sh
# 1. Submit dokumen (base64)
curl -X POST http://localhost:8080/api/travel/submit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{
    "document_type": "invoice",
    "source_system": "PISmart",
    "reference_id": "TRX-001",
    "filename": "hotel.pdf",
    "file_base64": "<base64>"
  }'
# → { "transaction_id": "...", "status": "processing" }

# 2. Poll hasil (ulangi sampai status bukan "processing")
curl "http://localhost:8080/api/travel/result/{transaction_id}" \
  -H "X-API-Key: your_key"
```

### PINTER API — Upload & Extract (SQLite Persistent)

```sh
# 1. Upload PDF
curl -X POST http://localhost:8080/api/pinter/upload \
  -H "X-API-Key: your_key" \
  -F "file=@invoice.pdf"
# → { "trx_id": "uuid", "status": "progress", "message": "..." }

# 2. Poll hasil (ulangi sampai status bukan "progress")
curl "http://localhost:8080/api/pinter/extract?trx_id={trx_id}" \
  -H "X-API-Key: your_key"
# → { "trx_id": "...", "status": "success", "message": "...", "data": { ... } }
```

**Keunggulan PINTER API vs `/api/travel/`**: hasil tersimpan di SQLite sehingga tetap tersedia meski server restart.

---

## Pembaruan Terkini

### v1.1 — PINTER API Upload & Extract (branch: `002-upload-extract-api`)

Menambahkan dua endpoint baru untuk integrasi PISmart → PINTER dengan penyimpanan persisten:

**Endpoint:**
- `POST /api/pinter/upload` — terima PDF multipart, return `trx_id` langsung
- `GET /api/pinter/extract?trx_id={trx_id}` — poll hasil ekstraksi dari SQLite
- Autentikasi via header `X-API-Key` (env var `PINTER_API_KEY`)
- TTL trx_id default 7 hari (env var `PINTER_TRX_TTL_DAYS`)

**File baru:**
- [`web/api/v1_upload.py`](web/api/v1_upload.py) — router PINTER dengan dependency auth + TTL check
- [`web/models/v1_upload.py`](web/models/v1_upload.py) — Pydantic models + custom exception `V1ApiError`
- [`web/db/sqlite.py`](web/db/sqlite.py) — async SQLite layer (`init_db`, `create_job`, `get_job`, `update_job`)
- [`web/db/__init__.py`](web/db/__init__.py) — package marker

**File diupdate:**
- [`web/main.py`](web/main.py) — registrasi router, inisialisasi SQLite saat startup, centralized error handler
- [`web/config.py`](web/config.py) — env var `SQLITE_DB_PATH`, `PINTER_API_KEY`, `PINTER_TRX_TTL_DAYS`
- [`web/API.md`](web/API.md) — dokumentasi endpoint PINTER
- `requirements.txt` — tambah `aiosqlite>=0.19.0`

**Format error konsisten** di semua endpoint `/api/pinter/`:
```json
{ "status": "fail", "message": "...", "error_code": "MACHINE_READABLE_CODE" }
```

Error codes: `MISSING_FILE`, `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `TRX_NOT_FOUND`, `TRX_EXPIRED`, `INTERNAL_ERROR`.

---

### v1.0.1 — Perbaikan Travel API — Doc Type Fallback Warning (branch: `001-add-travel-api-contract`)

Memperbaiki gap di endpoint `GET /api/travel/result/{transaction_id}`: ketika klasifikasi jenis dokumen gagal dan fallback ke `"hotel"`, peringatan kini dikembalikan ke PISmart via field `warning` (sebelumnya hanya di-log di server).

**Perubahan:** [`web/api/travel.py`](web/api/travel.py) — propagasi flag `doc_type_fallback` dari upload ke response poll.

---

## Format Hasil Ekstraksi

Kedua API mengembalikan hasil dalam format yang sama:

### FlightTicketResult

```json
{
  "receipt_number": "ABC123",
  "airline": "Garuda Indonesia",
  "route_from": "CGK",
  "route_to": "DPS",
  "flight_date": "2026-05-15",
  "total_payment": 1500000,
  "currency": "IDR",
  "authenticity": { ... }
}
```

### HotelInvoiceResult

```json
{
  "hotel_name": "Hotel Grand",
  "check_in_date": "2026-05-10",
  "check_out_date": "2026-05-12",
  "total_nights": 2,
  "total_payment": 800000,
  "currency": "IDR",
  "authenticity": { ... }
}
```

### DocumentAuthenticity

```json
{
  "verdict": "AUTENTIK",
  "is_suspicious": false,
  "confidence_score": 0.92,
  "fake_evidence": [],
  "warning_flags": [],
  "analysis_notes": "Dokumen terlihat asli."
}
```

`verdict` values: `AUTENTIK` | `MENCURIGAKAN` | `PALSU/DIEDIT`

---

## Struktur Proyek

```
invoice_verifier/          ← git root
├── requirements.txt
├── Dockerfile
├── web/                   ← aplikasi FastAPI
│   ├── main.py
│   ├── config.py
│   ├── API.md             ← dokumentasi API lengkap
│   ├── api/
│   │   ├── verify.py      ← /api/verify/
│   │   ├── travel.py      ← /api/travel/
│   │   └── v1_upload.py   ← /api/pinter/
│   ├── db/
│   │   └── sqlite.py      ← async SQLite layer
│   ├── models/
│   │   ├── responses.py
│   │   └── v1_upload.py
│   └── services/
│       └── agent_runner.py
├── baca_invoice/          ← AI agents (Google ADK)
│   ├── .env_example
│   └── agents/
└── data/                  ← SQLite database (auto-created, tidak di-commit)
    └── invoice_verifier.db
```

---

## Keterbatasan

- **Single-process only** — job state in-memory tidak bisa di-share antar worker/replica
- **Token job tidak persisten** — `JOB_SECRET_KEY` auto-generate saat startup jika tidak diset; set di `.env` agar token tetap valid setelah restart
- **Validasi PDF minimal** — hanya cek ekstensi dan magic bytes `%PDF`; PDF malformed bisa menyebabkan agent error
- **Tidak ada horizontal scaling** — untuk scale-out, gunakan task queue eksternal (Celery, ARQ)
