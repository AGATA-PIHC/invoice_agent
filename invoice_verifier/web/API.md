# Invoice Verifier — API Reference

Base URL: `http://localhost:8080`

---

## Authentication

Upload returns a `token` (HMAC-SHA256 of `job_id`). All subsequent job endpoints require
`?token=<token>` as a query parameter.

---

## Endpoints

### POST /api/verify/upload

Upload a PDF invoice for verification.

**Rate limit:** 10 requests / minute per IP

**Request:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | File | PDF file, max 20 MB |

**Response 200:**
```json
{
  "job_id": "3f8a1c2d-...",
  "filename": "invoice.pdf",
  "token": "a3f9b..."
}
```

**Error codes:** `400` invalid file, `413` file too large, `429` rate limited

---

### GET /api/verify/{job_id}/stream?token={token}

Server-Sent Events stream of agent activity. Reconnect-safe via `Last-Event-ID`.

**Event types:**

#### `status`
```json
{ "type": "status", "message": "Memulai verifikasi dokumen..." }
```

#### `agent_event`
```json
{ "type": "agent_event", "author": "coordinator_agent", "kind": "tool_call", "tool": "hotel_invoice_agent" }
{ "type": "agent_event", "author": "hotel_invoice_agent", "kind": "tool_result", "tool": "hotel_invoice_agent", "success": true }
{ "type": "agent_event", "author": "hotel_extractor_agent", "kind": "text", "text": "Extracting hotel data..." }
```

`kind` values: `tool_call` | `tool_result` | `text`

#### `complete`
```json
{
  "type": "complete",
  "result": { /* FlightTicketResult or HotelInvoiceResult — see below */ }
}
```

#### `error`
```json
{ "type": "error", "message": "Terjadi kesalahan saat memproses dokumen." }
```

**Keepalive:** SSE comments (`: keepalive`) are sent every 15 s to prevent proxy timeouts.

---

### GET /api/verify/{job_id}/status?token={token}

Poll job status without streaming.

**Response 200:**
```json
{
  "job_id": "3f8a1c2d-...",
  "status": "running",
  "filename": "invoice.pdf",
  "event_count": 5,
  "error": null
}
```

`status` values: `pending` | `running` | `done` | `error`

---

### GET /api/verify/{job_id}/result?token={token}

Retrieve the final parsed result.

**Response 200 (done):**
```json
{ "status": "done", "result": { /* FlightTicketResult or HotelInvoiceResult */ } }
```

**Response 200 (still running):**
```json
{ "status": "running", "result": null }
```

---

### GET /health

Liveness check for load balancers.

**Response 200:**
```json
{ "status": "ok", "jobs_active": 3 }
```

---

## Result Schemas

### FlightTicketResult (key fields)

| Field | Type |
|-------|------|
| `receipt_number` | string |
| `airline` | string |
| `route_from` / `route_to` | string |
| `flight_date` | string |
| `total_payment` | number |
| `currency` | string |
| `authenticity` | DocumentAuthenticity |

### HotelInvoiceResult (key fields)

| Field | Type |
|-------|------|
| `hotel_name` | string |
| `check_in_date` / `check_out_date` | string |
| `total_nights` | number |
| `total_payment` | number |
| `currency` | string |
| `authenticity` | DocumentAuthenticity |

### DocumentAuthenticity

| Field | Type | Values |
|-------|------|--------|
| `verdict` | string | `AUTENTIK` \| `MENCURIGAKAN` \| `PALSU/DIEDIT` |
| `is_suspicious` | boolean | |
| `confidence_score` | float | 0.0 – 1.0 |
| `fake_evidence` | string[] | |
| `warning_flags` | string[] | |
| `analysis_notes` | string | |

---

## Travel Integration API (PISmart → PINTER)

Endpoint khusus untuk integrasi mesin-ke-mesin antara **PISmart (A)** dan **PINTER (B)**.
Alur: kirim dokumen → terima `transaction_id` → poll hasil.

### Authentication

Set header `X-API-Key: <key>` pada setiap request.
Konfigurasi key via env var `TRAVEL_API_KEY`. Jika tidak diset, auth dinonaktifkan (development only).

---

### POST /api/travel/submit

Kirim dokumen PDF travel (invoice atau receipt) untuk diverifikasi.

**Request:** `application/json`

```json
{
  "document_type": "invoice",
  "source_system": "PISmart",
  "reference_id": "TRX-2026-0001",
  "filename": "hotel_invoice.pdf",
  "file_base64": "<base64-encoded PDF>"
}
```

| Field | Type | Deskripsi |
|-------|------|-----------|
| `document_type` | `"invoice"` \| `"receipt"` | `invoice` = tagihan, `receipt` = bukti bayar |
| `source_system` | string | Nama sistem pengirim |
| `reference_id` | string | ID transaksi dari sisi PISmart |
| `filename` | string | Nama file, harus berakhiran `.pdf` |
| `file_base64` | string | Isi file PDF di-encode base64 |

**Response 200:**
```json
{
  "transaction_id": "9f1a2b3c-...",
  "reference_id": "TRX-2026-0001",
  "status": "processing",
  "submitted_at": "2026-05-15T08:00:00+00:00"
}
```

**Error codes:** `400` validasi gagal, `401` API key salah

---

### GET /api/travel/result/{transaction_id}

Poll hasil verifikasi. Ulangi hingga `status` bukan `"processing"`.

**Response 200 (masih diproses):**
```json
{
  "transaction_id": "9f1a2b3c-...",
  "reference_id": "TRX-2026-0001",
  "document_type": "invoice",
  "status": "processing",
  "ocr_confidence": null,
  "result": null,
  "warning": null,
  "error": null,
  "completed_at": null
}
```

**Response 200 (selesai):**
```json
{
  "transaction_id": "9f1a2b3c-...",
  "reference_id": "TRX-2026-0001",
  "document_type": "invoice",
  "status": "completed",
  "ocr_confidence": 0.87,
  "result": { /* FlightTicketResult atau HotelInvoiceResult — lihat Result Schemas */ },
  "warning": null,
  "error": null,
  "completed_at": "2026-05-15T08:00:45+00:00"
}
```

**Response 200 (confidence rendah — tetap dikembalikan, tidak jadi stopper):**
```json
{
  "status": "completed",
  "ocr_confidence": 0.45,
  "result": { /* data parsial */ },
  "warning": "OCR confidence rendah (45%), disarankan review manual.",
  "error": null
}
```

**Response 200 (gagal — tidak throw 500):**
```json
{
  "status": "failed",
  "ocr_confidence": null,
  "result": null,
  "warning": null,
  "error": "Terjadi kesalahan saat memproses dokumen."
}
```

`status` values: `processing` | `completed` | `failed`

**Error codes:** `401` API key salah, `404` transaction_id tidak ditemukan

---

### Catatan Desain

- **Non-blocking**: POST /submit langsung return `transaction_id`, proses OCR berjalan di background.
- **Jangan jadi stopper**: Hasil selalu dikembalikan meski OCR gagal atau confidence rendah. PISmart tetap bisa melanjutkan prosesnya.
- **Distinction Invoice vs Receipt**: Field `document_type` di-echo back ke response. Konten OCR (data tiket/hotel) sama untuk keduanya.
- **Fallback doc_type**: Jika auto-detect gagal mengenali jenis dokumen, sistem fallback ke `"hotel"` daripada menolak request.
- **Polling interval**: Disarankan poll setiap 3–5 detik. Rata-rata waktu proses 10–30 detik tergantung dokumen.

---

---

## API v1 — PISmart Integration (Upload & Extract)

Endpoint machine-to-machine antara **PISmart (A)** dan **PINTER (B)**.
Hasil ekstraksi disimpan persisten di **SQLite** — tersedia meski server restart.

### POST /api/v1/upload

Upload file PDF invoice/receipt untuk diekstraksi.

**Request:** `multipart/form-data`

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `file` | File (PDF) | File PDF, maks 20 MB |

**Response 200:**
```json
{ "trx_id": "uuid", "status": "progress", "message": "Dokumen diterima dan sedang diproses." }
```

**Error codes:** `400` file tidak valid / bukan PDF, `413` file terlalu besar, `500` internal error

---

### GET /api/v1/extract/{trx_id}

Poll hasil ekstraksi. Ulangi hingga `status` bukan `"progress"`.

**Response 200 (progress):**
```json
{ "trx_id": "uuid", "status": "progress", "message": "Dokumen sedang diproses.", "data": null }
```

**Response 200 (success):**
```json
{
  "trx_id": "uuid",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": { /* seluruh JSON hasil agent — FlightTicketResult atau HotelInvoiceResult */ }
}
```

**Response 200 (fail):**
```json
{ "trx_id": "uuid", "status": "fail", "message": "Ekstraksi gagal: ...", "data": null }
```

**Error codes:** `404` trx_id tidak ditemukan, `500` internal error

### Format Error Konsisten (semua endpoint /api/v1/)

```json
{ "status": "fail", "message": "pesan human-readable", "error_code": "MACHINE_READABLE_CODE" }
```

| error_code | HTTP | Kondisi |
|---|---|---|
| `MISSING_FILE` | 400 | Field file tidak ada |
| `INVALID_FILE_TYPE` | 400 | Bukan PDF |
| `FILE_TOO_LARGE` | 413 | Melebihi batas ukuran |
| `TRX_NOT_FOUND` | 404 | trx_id tidak dikenal |
| `INTERNAL_ERROR` | 500 | Error internal server |

### Catatan Desain v1

- **Persistent**: Hasil disimpan di SQLite (`SQLITE_DB_PATH`) — tersedia meski server restart.
- **Non-blocking**: POST /upload langsung return `trx_id`, proses berjalan di background.
- **Data lengkap**: Field `data` berisi seluruh output JSON dari AI agent tanpa disaring.
- **Polling interval**: Disarankan poll setiap 3–5 detik.

---

## Known Limitations

- **No persistent auth** — `JOB_SECRET_KEY` is auto-generated on startup if not set in `.env`,
  meaning job tokens are invalidated on server restart. Set `JOB_SECRET_KEY` in `.env` for persistence.
- **Single-process only** — In-memory job state cannot be shared across multiple workers/replicas.
- **No horizontal scaling** — Run a single process or use an external task queue (Celery, ARQ) for scale-out.
- **PDF content validation** — Only extension and size are checked; malformed PDFs may cause agent errors.
