# PINTER ↔ PISmart API Contract

Versi: 1.0 (draft) · Tanggal: 2026-05-19 · Tracking: [ADS-16](https://linear.app/agata-pihc/issue/ADS-16)

Dokumen ini adalah kontrak resmi antara **PISmart (A)** sebagai konsumen dan
**PINTER (B)** sebagai penyedia layanan ekstraksi dokumen perjalanan (tiket pesawat /
invoice hotel / bukti bayar). Kontrak ini bersifat asynchronous dengan pola
**upload → polling**: PISmart meng-upload PDF, menerima `trx_id`, lalu polling
endpoint extract sampai status `success` atau `fail`.

> **Status implementasi.** Endpoint yang sudah berjalan di repo ini hari ini
> adalah `/api/verify/*` (lihat `invoice_verifier/web/API.md`). Endpoint
> `/api/pinter/*` yang dijelaskan di kontrak ini **belum diimplementasikan** dan
> akan dibuat sebagai integrasi terpisah untuk PISmart — direkomendasikan sebagai
> thin facade di atas service `agent_runner` yang sudah ada. Lihat bagian
> *Mapping ke implementasi existing* di akhir dokumen.

---

## 1. Ringkasan endpoint

| # | Method | Path                              | Tujuan                                  |
|---|--------|-----------------------------------|------------------------------------------|
| 1 | POST   | `/api/pinter/upload`              | Upload PDF, dapatkan `trx_id`            |
| 2 | GET    | `/api/pinter/extract?trx_id=...`  | Polling hasil ekstraksi by `trx_id`      |

Base URL produksi (placeholder): `https://pinter.<env>.internal/`
Versi API dibawa di path (`/api/pinter/...`); kenaikan versi major → prefix baru
`/api/v2/pinter/...`.

---

## 2. Status enum (berlaku di kedua endpoint)

| Nilai      | Arti                                                                 |
|------------|----------------------------------------------------------------------|
| `progress` | Dokumen masih diproses. PISmart wajib polling lagi.                  |
| `success`  | Ekstraksi selesai, payload `data` tersedia.                          |
| `fail`     | Ekstraksi gagal permanen. `message` berisi alasan, `data` = `null`.  |

Aturan transisi: `progress` → `success` | `fail`. Setelah `success`/`fail`
status tidak akan berubah lagi sampai `trx_id` kedaluwarsa.

---

## 3. Autentikasi antar service

- **Skema:** Bearer token via header `Authorization: Bearer <PINTER_API_KEY>`.
- **Distribusi key:** static API key per environment (`dev`, `staging`, `prod`),
  disimpan PISmart di secret manager, di-rotasi minimal setiap 90 hari atau
  saat ada indikasi kebocoran.
- **Identifikasi pemanggil:** header opsional `X-Client-Id: pismart` untuk
  observability/log. Wajib jika ada lebih dari satu konsumen di masa depan.
- **Idempotency:** header opsional `Idempotency-Key: <uuid>` pada upload untuk
  mencegah duplikasi saat retry. Jika diberikan dan key sama dikirim ulang
  dalam 24 jam, PINTER mengembalikan `trx_id` yang sama (HTTP 200, bukan 201).
- **Transport:** HTTPS only. Permintaan via HTTP plain ditolak dengan 400.
- **CORS:** endpoint server-to-server, tidak meng-allow origin browser.

> Untuk integrasi user-facing yang sudah ada (`/api/verify/*`), skema HMAC
> per-job token tetap dipakai. Skema Bearer di kontrak ini hanya berlaku untuk
> kanal PINTER ↔ PISmart.

---

## 4. Endpoint #1 — Upload

```
POST /api/pinter/upload
Authorization: Bearer <PINTER_API_KEY>
Content-Type: multipart/form-data
Idempotency-Key: <uuid>           (opsional, recommended)
X-Client-Id: pismart              (opsional)
```

### 4.1 Request body (multipart form)

| Field    | Tipe   | Wajib | Keterangan                                                            |
|----------|--------|-------|-----------------------------------------------------------------------|
| `file`   | file   | ya    | Dokumen PDF (invoice / receipt / bukti bayar).                        |
| `doc_hint` | string | tidak | Hint tipe dokumen: `flight` \| `hotel` \| `auto`. Default `auto`. |

### 4.2 Validasi file upload

| Aturan                | Nilai                                                                 |
|-----------------------|------------------------------------------------------------------------|
| MIME type yang diterima | `application/pdf` (cek magic bytes `%PDF-`, bukan hanya ekstensi).   |
| Ekstensi              | `.pdf` (case-insensitive).                                             |
| Ukuran maksimum       | **20 MB** per file. Selaras dengan `MAX_UPLOAD_MB` di `web/config.py`. |
| Jumlah halaman maks   | 50 halaman (proteksi terhadap PDF balon).                              |
| Encrypted PDF         | Ditolak (400 `ENCRYPTED_PDF`).                                         |
| Filename              | Dibersihkan, hanya basename yang dipakai. Karakter path-traversal di-reject. |
| Per-IP rate limit     | 10 upload / menit (mengikuti policy `/api/verify/upload`).             |
| Per-API-key rate limit | 60 upload / menit.                                                    |

### 4.3 Response 202 (Accepted)

> Mengembalikan **202 Accepted**, bukan 200, karena pemrosesan masih berjalan.

```json
{
  "trx_id": "3f8a1c2d-7e1f-4b5a-9c3d-1a2b3c4d5e6f",
  "status": "progress",
  "message": "Dokumen diterima, ekstraksi sedang berjalan.",
  "expires_at": "2026-05-19T05:31:29Z",
  "poll": {
    "url": "/api/pinter/extract?trx_id=3f8a1c2d-7e1f-4b5a-9c3d-1a2b3c4d5e6f",
    "interval_ms": 2000,
    "timeout_ms": 120000
  }
}
```

| Field          | Tipe     | Keterangan                                                              |
|----------------|----------|-------------------------------------------------------------------------|
| `trx_id`       | string (UUIDv4) | Disimpan di DB PISmart, dipakai sebagai key polling.            |
| `status`       | enum     | Selalu `progress` di response upload (kecuali validasi sinkron gagal).  |
| `message`      | string   | Deskriptif, aman untuk ditampilkan ke user akhir.                       |
| `expires_at`   | RFC3339  | Setelah waktu ini, `trx_id` tidak bisa lagi di-poll.                    |
| `poll.interval_ms` | int  | Interval polling yang **direkomendasikan**.                             |
| `poll.timeout_ms`  | int  | Total budget polling yang **direkomendasikan**.                         |

### 4.4 Error sinkron (response upload langsung gagal)

Jika validasi gagal sebelum job dibuat, PINTER mengembalikan struktur error
standar (lihat §6) dengan `status: "fail"` dan tanpa `trx_id`.

---

## 5. Endpoint #2 — Extract (polling)

```
GET /api/pinter/extract?trx_id=<uuid>
Authorization: Bearer <PINTER_API_KEY>
```

### 5.1 Query parameter

| Param    | Wajib | Keterangan                                |
|----------|-------|--------------------------------------------|
| `trx_id` | ya    | UUID yang didapat dari endpoint upload.    |

### 5.2 Response 200 — `progress`

```json
{
  "trx_id": "3f8a1c2d-...",
  "status": "progress",
  "message": "Ekstraksi masih berjalan.",
  "data": null,
  "progress_pct": 35,
  "retry_after_ms": 2000
}
```

PISmart **harus** menghormati `retry_after_ms` (atau header HTTP
`Retry-After` jika ada) untuk backoff.

### 5.3 Response 200 — `success`

```json
{
  "trx_id": "3f8a1c2d-...",
  "status": "success",
  "message": "Ekstraksi selesai.",
  "doc_type": "flight",                
  "data": { /* FlightTicketResult | HotelInvoiceResult — §5.5 */ }
}
```

| Field      | Keterangan                                              |
|------------|---------------------------------------------------------|
| `doc_type` | `flight` \| `hotel`. Menentukan skema `data`.           |
| `data`     | Objek hasil ekstraksi, skema bergantung `doc_type`.     |

### 5.4 Response 200 — `fail`

```json
{
  "trx_id": "3f8a1c2d-...",
  "status": "fail",
  "message": "Dokumen tidak dikenali sebagai tiket pesawat atau invoice hotel.",
  "error": {
    "code": "UNSUPPORTED_DOCUMENT",
    "retriable": false,
    "hint": "Pastikan PDF berasal dari Traveloka, tiket.com, Garuda, dst."
  },
  "data": null
}
```

### 5.5 Skema `data`

Skema `data` mengikuti Pydantic model di repo:

- `doc_type = "flight"` → `FlightTicketResult` (`invoice_verifier/baca_invoice/models/flight.py`).
- `doc_type = "hotel"` → `HotelInvoiceResult` (`invoice_verifier/baca_invoice/models/hotel.py`).

Setiap objek `data` mengandung sub-objek `authenticity`
(`DocumentAuthenticity`, lihat `authenticity.py`) dengan field-field kunci:

| Field                | Tipe    | Nilai                                        |
|----------------------|---------|----------------------------------------------|
| `verdict`            | string  | `AUTENTIK` \| `MENCURIGAKAN` \| `PALSU/DIEDIT` |
| `is_suspicious`      | bool    |                                              |
| `confidence_score`   | float   | 0.0 – 1.0                                    |
| `fake_evidence`      | string[] | Bukti konkret indikasi palsu/edit.          |
| `warning_flags`      | string[] |                                              |
| `analysis_notes`     | string  |                                              |

Field tambahan di `data`: `extraction_confidence` (0–1),
`requires_manual_review` (bool), `review_reasons` (string[]), `summary`.

Sumber kebenaran skema adalah Pydantic model di kode. Setiap perubahan field
**wajib** dibarengi bump versi minor (lihat §10).

---

## 6. Error schema standar

Semua error — sinkron (upload) maupun terminal (`status: "fail"` pada extract) —
menggunakan envelope berikut:

```json
{
  "status": "fail",
  "message": "Pesan ramah-user dalam Bahasa Indonesia.",
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "retriable": false,
    "hint": "Saran tindakan, opsional."
  },
  "trx_id": null,
  "data": null
}
```

### 6.1 Mapping kode error ↔ HTTP status

| HTTP | `error.code`              | Penyebab                                                 | `retriable` |
|------|----------------------------|----------------------------------------------------------|-------------|
| 400  | `INVALID_FILE`             | Bukan PDF / ekstensi salah / nama file invalid.          | false       |
| 400  | `ENCRYPTED_PDF`            | PDF terenkripsi/password-protected.                       | false       |
| 400  | `MISSING_FIELD`            | Field wajib (mis. `file`, `trx_id`) tidak ada.            | false       |
| 401  | `UNAUTHENTICATED`          | Header `Authorization` hilang/invalid.                    | false       |
| 403  | `FORBIDDEN`                | API key valid tapi tidak punya akses.                     | false       |
| 404  | `TRX_NOT_FOUND`            | `trx_id` tidak ada / tidak pernah dibuat.                 | false       |
| 410  | `TRX_EXPIRED`              | `trx_id` sudah lewat `expires_at` (lihat §7).             | false       |
| 413  | `FILE_TOO_LARGE`           | Ukuran file > 20 MB.                                      | false       |
| 415  | `UNSUPPORTED_MEDIA_TYPE`   | MIME bukan `application/pdf`.                             | false       |
| 422  | `UNSUPPORTED_DOCUMENT`     | PDF valid tapi bukan tiket pesawat / invoice hotel.       | false       |
| 422  | `EXTRACTION_FAILED`        | Agent gagal mengekstrak setelah retry internal.           | false       |
| 429  | `RATE_LIMITED`             | Melewati per-IP atau per-key rate limit.                  | true        |
| 500  | `INTERNAL_ERROR`           | Bug PINTER. PISmart boleh retry dengan backoff.           | true        |
| 502  | `UPSTREAM_ERROR`           | Gemini/LLM upstream gagal sementara.                      | true        |
| 503  | `SERVICE_UNAVAILABLE`      | Maintenance / overload terkontrol.                        | true        |
| 504  | `UPSTREAM_TIMEOUT`         | LLM tidak merespons dalam batas waktu internal.           | true        |

Aturan: response **5xx** dan **429** mengandung header `Retry-After`
(detik). PISmart harus retry dengan exponential backoff (mis. 2s, 4s, 8s,
maksimum 3 kali) hanya jika `retriable: true`.

---

## 7. Mekanisme polling

| Parameter                  | Nilai default | Rekomendasi PISmart                                 |
|----------------------------|---------------|-----------------------------------------------------|
| Interval polling           | 2.000 ms      | Pakai `poll.interval_ms` dari response upload.      |
| Backoff saat `progress`    | Linear / konstan; jangan lebih agresif dari interval. |                                          |
| Total timeout client       | 120.000 ms (2 menit) | Jika lewat, hentikan polling dan tandai job stuck. |
| `trx_id` TTL (server-side) | **30 menit** sejak upload | Setelah lewat, GET extract → 410 `TRX_EXPIRED`. |
| Hasil `success`/`fail` retention | 30 menit setelah selesai | Idempotent: poll ulang dalam window ini boleh, hasil sama. |
| Backoff saat 429 / 5xx     | Exponential (2/4/8 s), max 3 retry. |                                            |

PISmart **tidak boleh** polling lebih cepat dari `retry_after_ms` yang dikirim
server, untuk menghindari rate-limit.

---

## 8. Webhook / callback (evaluasi alternatif polling)

**Keputusan v1.0:** *tidak* didukung. Polling tetap mekanisme utama.

**Alasan:**
- PISmart menjalankan flow user-interaktif yang sudah menunggu hasil (waktu
  ekstraksi median 5–20 detik) — polling 2 detik sudah memberikan latensi
  yang dapat diterima.
- Webhook menambah beban operasional: PINTER perlu retry queue dengan DLQ,
  signature verification (HMAC), public ingress di sisi PISmart, dan
  reconciliation untuk delivery yang miss.
- Tidak ada kebutuhan batch / fire-and-forget di scope saat ini.

**Roadmap v2.0 (opsional, jika muncul batch use-case):**

Webhook tambahan, bukan pengganti polling, dengan kontrak:

```
POST <pismart_callback_url>
X-PINTER-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>
Content-Type: application/json

{ "trx_id": "...", "status": "success" | "fail", "data": { ... } }
```

- Signature: HMAC-SHA256 atas `t.<raw_body>` dengan shared secret per-tenant.
- Retry: 5x dengan exponential backoff (1m, 5m, 30m, 2h, 12h); setelah itu
  masuk DLQ + alert ke ops.
- PISmart tetap boleh polling sebagai fallback rekonsiliasi.

Item ini di-track terpisah; **tidak** dirilis di v1.0.

---

## 9. Contoh end-to-end

```bash
# 1. Upload
curl -X POST https://pinter.staging.internal/api/pinter/upload \
  -H "Authorization: Bearer $PINTER_API_KEY" \
  -H "Idempotency-Key: 7c6c1a9e-..." \
  -F "file=@invoice.pdf"

# → 202
# { "trx_id": "3f8a1c2d-...", "status": "progress",
#   "message": "Dokumen diterima, ekstraksi sedang berjalan.",
#   "expires_at": "2026-05-19T05:31:29Z",
#   "poll": { "url": "/api/pinter/extract?trx_id=3f8a1c2d-...",
#             "interval_ms": 2000, "timeout_ms": 120000 } }

# 2. Polling sampai status != "progress"
curl "https://pinter.staging.internal/api/pinter/extract?trx_id=3f8a1c2d-..." \
  -H "Authorization: Bearer $PINTER_API_KEY"

# → 200 (progress)  → tunggu interval_ms → ulangi
# → 200 (success)   → simpan `data` di DB, selesai
# → 200 (fail)      → tampilkan `error.hint` ke user
```

---

## 10. Versioning & breaking change policy

- Versi mengikuti SemVer di field meta `X-API-Version` (header response).
- **Minor**: penambahan field opsional, error code baru → backward-compatible.
- **Major**: perubahan field wajib / penghapusan field / rename → path baru
  (`/api/v2/pinter/...`), minimal 30 hari overlap dengan v1.
- Tambah field di `data` (FlightTicketResult / HotelInvoiceResult) = minor.
  PISmart harus tolerant terhadap field baru yang tidak dikenal.

---

## 11. Mapping ke implementasi existing

Implementasi saat ini di `invoice_verifier/web/api/verify.py` sudah memiliki
seluruh kapabilitas yang dibutuhkan kontrak ini, tinggal dibungkus dengan
nama/path/status yang sesuai. Mapping yang disarankan untuk implementasi
endpoint `/api/pinter/*`:

| Konsep PINTER kontrak       | Implementasi existing                                  |
|-----------------------------|--------------------------------------------------------|
| `trx_id`                    | `job_id` (UUID dari `uuid.uuid4()`).                   |
| `POST /api/pinter/upload`   | Reuse `upload_file()` + `agent_runner.create_job()` + `run_job()`. |
| `GET  /api/pinter/extract`  | Reuse `agent_runner.get_job()` (status + result dalam satu call). |
| Status `progress`           | Map dari `JobStatus.PENDING` / `JobStatus.RUNNING`.     |
| Status `success`            | Map dari `JobStatus.DONE` (alias `done`).               |
| Status `fail`               | Map dari `JobStatus.ERROR` + validasi sinkron yg gagal. |
| `expires_at`                | `created_at + 30m` (perlu ditambahkan ke job state).    |
| Auth Bearer                 | Middleware baru; HMAC per-job token existing tidak dipakai di kanal ini. |
| Rate limit per-key          | Tambahan limiter berdasarkan API key (`X-Client-Id`).   |

Endpoint `/api/verify/*` yang sudah ada **tetap dipertahankan** untuk UI
internal — tidak ada breaking change di sisi user.
