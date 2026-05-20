# Invoice Verifier — PINTER

Layanan verifikasi dokumen perjalanan dinas (invoice & receipt) menggunakan AI Agent berbasis Google Gemini.
Mendukung integrasi mesin-ke-mesin dengan sistem eksternal (PISmart).

---

## Endpoint API

| # | Method | Path | Fungsi |
|---|--------|------|--------|
| 1 | `POST` | `/api/pinter/upload` | Upload PDF → return `trx_id` (proses async di background) |
| 2 | `GET` | `/api/pinter/extract?trx_id={trx_id}` | Poll hasil ekstraksi dari SQLite |
| 3 | `GET` | `/health` | Liveness check operasional |

Autentikasi: header `X-API-Key` (env `PINTER_API_KEY`, nonaktif jika tidak diset).

---

## Klasifikasi Dokumen (2-Stage)

Sistem mengklasifikasikan dokumen dalam **dua tahap independen**:

```
                  ┌─────────────────────┐
                  │  Stage 1: doc_type  │  classify_document()
                  └──────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   "invoice"            "receipt"             "unknown"
        │                    │                    │
        ▼                    ▼                    ▼
  ┌──────────┐         ┌──────────┐       ┌────────────┐
  │ Stage 2  │         │ Stage 2  │       │  Skip AI   │
  │ sub_type │         │ sub_type │       │  + return  │
  └────┬─────┘         └────┬─────┘       │ Unknown    │
       │                    │             │ Result     │
   hotel / None         flight / None     └────────────┘
       │                    │
       ▼                    ▼
  invoice_agent        receipt_agent
   atau                 atau
  hotel_agent          flight_agent
```

**Stage 1 — `classify_document()`** → `"invoice"` / `"receipt"` / `"unknown"`
- Keyword invoice: `invoice`, `faktur`, `tagihan`, `ppn`, `vat`, `npwp`, `jatuh tempo`, …
- Keyword receipt: `receipt`, `struk`, `bukti bayar`, `kwitansi`, `e-tiket`, `paid`, …
- `unknown` → tidak memanggil AI, langsung return `UnknownResult` + hasil `authenticity`

**Stage 2 — `classify_sub_type()`** → `"hotel"` / `"flight"` / `None`
- Hanya untuk routing internal — `doc_type` di response tetap invoice/receipt
- Keyword hotel: `hotel`, `penginapan`, `kamar`, `check-in`, …
- Keyword flight: `pesawat`, `flight`, `tiket`, `garuda`, `airasia`, …

**Routing agent:**
- `hotel` → `hotel_agent` (ekstraktor spesifik invoice hotel)
- `flight` → `flight_agent` (ekstraktor spesifik tiket pesawat)
- invoice tanpa sub_type → `invoice_agent` (generic)
- receipt tanpa sub_type → `receipt_agent` (generic)

---

## Persyaratan

- Python 3.11+
- Google AI Studio API key (atau Vertex AI)

---

## Konfigurasi

Salin `baca_invoice/.env_example` ke `baca_invoice/.env` dan isi:

| Variabel | Keterangan | Default |
|----------|------------|---------|
| `GOOGLE_API_KEY` | API key Google AI Studio | — (wajib) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` untuk Vertex AI, `0` untuk AI Studio | `0` |
| `PINTER_API_KEY` | API key untuk header `X-API-Key` | — (opsional, nonaktif jika tidak diset) |
| `PINTER_TRX_TTL_DAYS` | TTL `trx_id` dalam hari → `TRX_EXPIRED` setelahnya | `7` |
| `SQLITE_DB_PATH` | Path file SQLite | `data/invoice_verifier.db` |
| `MAX_UPLOAD_MB` | Batas ukuran file upload | `20` |
| `MAX_CONCURRENT_JOBS` | Maksimum job AI yang berjalan paralel | `5` |

---

## Menjalankan

```sh
# Install dependensi
pip install -r requirements.txt

# Jalankan server
python run_web.py
# atau:
uvicorn web.main:app --host 0.0.0.0 --port 8080
```

Atau Docker:
```sh
docker build -t invoice-verifier .
docker run -p 8080:8080 --env-file baca_invoice/.env invoice-verifier
```

---

## Penggunaan API

### 1. Upload PDF

```sh
curl -X POST http://localhost:8080/api/pinter/upload \
  -H "X-API-Key: your_key" \
  -F "file=@invoice.pdf"
```

Response saat doc_type invoice/receipt:
```json
{
  "trx_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "progress",
  "message": "Dokumen diterima dan sedang diproses."
}
```

Response saat doc_type unknown:
```json
{
  "trx_id": "...",
  "status": "progress",
  "message": "Dokumen diterima. Tidak dikenali sebagai invoice/receipt — akan dikembalikan dengan doc_type='unknown'."
}
```

### 2. Poll Hasil

```sh
curl "http://localhost:8080/api/pinter/extract?trx_id={trx_id}" \
  -H "X-API-Key: your_key"
```

**Status `success`** (doc_type=invoice):
```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "invoice",
    "invoice_number": "INV-2026/001",
    "vendor_name": "PT Hotel Indah",
    "total_payment": 1887000.0,
    "currency": "IDR",
    "authenticity": { "verdict": "AUTENTIK", ... },
    "summary": "Invoice PT Hotel Indah, INV-2026/001, Total: Rp 1.887.000."
  }
}
```

**Status `success`** (doc_type=unknown, no AI):
```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "unknown",
    "authenticity": { ... },
    "extraction_confidence": 0.0,
    "requires_manual_review": true,
    "review_reasons": ["Dokumen tidak dikenali sebagai invoice atau receipt."],
    "summary": "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
  }
}
```

---

## Pydantic Models

| Model | doc_type | File |
|-------|----------|------|
| `TravelDocumentResult` | `"invoice"` / `"receipt"` / `"unknown"` | [`baca_invoice/models/travel_document.py`](baca_invoice/models/travel_document.py) |
| `DocumentAuthenticity` | shared | [`baca_invoice/models/authenticity.py`](baca_invoice/models/authenticity.py) |

`doc_type` dan `document_subtype` selalu ada di setiap response `success`. Semua hasil memakai satu schema gabungan; field yang tidak relevan tetap hadir dengan default `"-"`, `0.0`, `false`, atau `[]`.

---

## Validasi & Keamanan

- **PDF magic bytes** — file harus diawali `%PDF` (ekstensi `.pdf` saja tidak cukup)
- **Batas ukuran** — default 20 MB (env `MAX_UPLOAD_MB`)
- **Rate limit** — 10 upload per IP per menit (in-process sliding window)
- **Path traversal protection** — `dest_path` divalidasi relatif ke `UPLOAD_DIR`
- **TTL** — `trx_id` kedaluwarsa 7 hari (env `PINTER_TRX_TTL_DAYS`) → error `TRX_EXPIRED`
- **API Key** — header `X-API-Key` (env `PINTER_API_KEY`), nonaktif kalau tidak diset
- **Recovery on restart** — job yang stuck di status `progress` saat server restart otomatis ditandai `fail`

---

## Error Codes

Format response error konsisten:
```json
{ "status": "fail", "message": "...", "error_code": "MACHINE_READABLE_CODE" }
```

| Code | HTTP | Penyebab |
|------|------|----------|
| `MISSING_FILE` | 400 | Field `file` kosong di `POST /api/pinter/upload` |
| `MISSING_TRX_ID` | 400 | Query `trx_id` kosong di `GET /api/pinter/extract` |
| `VALIDATION_ERROR` | 400 | Validation error lain (field type/format salah) |
| `INVALID_FILE_TYPE` | 400 | Bukan PDF (ekstensi/magic bytes) |
| `FILE_TOO_LARGE` | 413 | Melebihi `MAX_UPLOAD_MB` |
| `RATE_LIMITED` | 429 | Lebih dari 10 upload/menit/IP |
| `TRX_NOT_FOUND` | 404 | trx_id tidak ada di DB |
| `TRX_EXPIRED` | 410 | trx_id sudah > `PINTER_TRX_TTL_DAYS` |
| `INTERNAL_ERROR` | 500 | Error tak terduga (DB/filesystem) |
| `UNAUTHORIZED` | 401 | X-API-Key salah/tidak ada |

---

## Arsitektur

```
                  ┌────────────────┐
                  │   FastAPI app  │
                  │  (web/main.py) │
                  └────────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
   POST /api/pinter/upload    GET /api/pinter/extract
        (multipart PDF)             (query param)
              │                         │
              ▼                         ▼
   ┌──────────────────┐      ┌──────────────────┐
   │ classify_document│      │   SQLite DB      │
   │ classify_sub_type│      │ (upload_jobs)    │
   └────────┬─────────┘      └──────────────────┘
            │
   doc_type=unknown? ─── Yes ──► _persist_unknown() (no AI)
            │
            No
            │
            ▼
   ┌──────────────────────────┐
   │   AgentRunnerService     │
   │  4 Runner (Google ADK):  │
   │  • invoice_agent         │
   │  • receipt_agent         │
   │  • hotel_agent           │
   │  • flight_agent          │
   └────────┬─────────────────┘
            │
            ▼
   ┌──────────────────┐
   │  Google Gemini   │
   │  2.5 Flash       │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  update_job()    │
   │  (SQLite)        │
   └──────────────────┘
```

---

## Struktur Proyek

```
invoice_verifier/                       ← git root
├── README.md
├── Dockerfile
├── web/                                ← aplikasi FastAPI
│   ├── main.py                         ← entry point + error handlers
│   ├── config.py                       ← env vars
│   ├── api/
│   │   └── v1_upload.py                ← endpoint /api/pinter/
│   ├── db/
│   │   └── sqlite.py                   ← async SQLite layer
│   ├── models/
│   │   ├── v1_upload.py                ← Pydantic request/response
│   │   └── responses.py                ← HealthResponse
│   └── services/
│       └── agent_runner.py             ← AgentRunnerService + classifier
└── baca_invoice/                       ← AI agents (Google ADK)
    ├── agents/
    │   ├── invoice.py                  ← invoice_agent (NEW)
    │   ├── receipt.py                  ← receipt_agent (NEW)
    │   ├── hotel.py                    ← hotel_agent (sub_type=hotel)
    │   ├── flight.py                   ← flight_agent (sub_type=flight)
    │   └── prompts.py                  ← INVOICE_PROMPT, RECEIPT_PROMPT, …
    ├── models/
    │   ├── invoice.py                  ← InvoiceResult (NEW)
    │   ├── receipt.py                  ← ReceiptResult (NEW)
    │   ├── unknown.py                  ← UnknownResult (NEW)
    │   ├── hotel.py                    ← HotelInvoiceResult
    │   ├── flight.py                   ← FlightTicketResult
    │   └── authenticity.py             ← DocumentAuthenticity
    └── tools/
        ├── authenticity.py             ← analyze_document_authenticity
        ├── pdf.py                      ← PyMuPDF metadata extraction
        └── constants.py                ← SOFTWARE_LABELS, KNOWN_PROVIDERS
```

---

## Testing

```sh
pytest tests/ -q
# 39 passed (unit + integration + security)
```

Test struktur:
- `tests/unit/` — model defaults, Job lifecycle
- `tests/integration/` — full HTTP flow (upload, extract, rate limit)
- `tests/security/` — path traversal, file validation, auth

---

## Pembaruan Terkini

### Spec 001 — Invoice & Receipt Classification (current)

Mengubah klasifikasi dari `flight`/`hotel` → `invoice`/`receipt`/`unknown` sebagai output utama API, dengan **2-stage classifier**:
- Stage 1: invoice/receipt/unknown (output API)
- Stage 2: hotel/flight/None (routing agent internal)

**Baru:**
- Model: `InvoiceResult`, `ReceiptResult`, `UnknownResult` (Pydantic v2)
- Agent: `invoice_agent`, `receipt_agent` (generic) + tetap memakai `hotel_agent`/`flight_agent` untuk dokumen spesifik
- Unknown doc → skip AI, langsung return `UnknownResult` + hasil `authenticity`
- Field `doc_type` selalu ada di response `success`

Lihat: [`specs/001-invoice-receipt-classification/`](specs/001-invoice-receipt-classification/)

### Konsolidasi v1 — PINTER-only

- Endpoint `/api/verify/` dan `/api/travel/` **dihapus**
- API tunggal: `/api/pinter/upload` + `/api/pinter/extract`
- SQLite persistent — hasil tetap tersedia setelah server restart
- Rate limiter built-in (10/min/IP)
- Stale job recovery saat startup

---

## Keterbatasan

- **Single-process** — state SQLite + rate limiter in-memory per-instance
- **No horizontal scaling out-of-the-box** — untuk multi-worker pakai task queue eksternal (Celery, ARQ)
- **PDF validation minimal** — magic bytes `%PDF` saja; PDF malformed bisa memicu agent error
- **Heuristic classifier** — keyword-based, akurasi tergantung kualitas teks PDF
