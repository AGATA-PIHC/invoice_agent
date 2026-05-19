# Implementation Plan: Frontend & Error Response Consistency

**Branch**: `002-upload-extract-api` (lanjut di branch ini) | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

## Summary

Memperbaiki dua inkonsistensi pasca-konsolidasi PINTER:
1. Frontend (`web/static/js/app.js`) di-rewrite ke endpoint `/api/pinter/*` dengan polling, mendukung schema invoice/receipt/unknown.
2. Backend menambah handler `RequestValidationError` agar error 422 FastAPI berformat seragam.

## Technical Context

| Item | Nilai |
|------|-------|
| **Frontend** | Vanilla JS (ES2020+), Fetch API, no build step |
| **Backend** | FastAPI (sudah ada), `RequestValidationError` dari `fastapi.exceptions` |
| **Polling** | `setTimeout` recursive di JS, interval 1.5s |
| **Test framework** | pytest + httpx (sudah ada) |
| **Tidak ada dependency baru** | ✓ |

**Tidak ada NEEDS CLARIFICATION** — semua keputusan teknis sudah diputuskan di Phase 0.

## Constitution Check

Tidak ada `.specify/memory/constitution.md`. Mengacu pada prinsip implisit:
- API contract tidak boleh breaking → ✓ FR-8 mengamanatkan ini
- Pendekatan testable → ✓ semua FR memiliki acceptance criteria
- Tidak menambah dependency baru jika bisa pakai yang ada → ✓
- UI rendering konsisten dengan data dari API → ✓

**Status**: PASS

## Project Structure

### Documentation (this feature)

```
specs/002-frontend-error-consistency/
├── spec.md                  # Feature specification
├── plan.md                  # This file
├── research.md              # Tech decisions
├── data-model.md            # (skipped — tidak ada entity baru)
├── contracts/
│   └── error-format.md      # Error response contract
├── quickstart.md            # Dev quick start
└── checklists/
    └── requirements.md
```

### Source Code (yang akan disentuh)

```
invoice_verifier/
├── web/
│   ├── api/
│   │   └── v1_upload.py        # MODIFY: tambah validation_exception_handler
│   ├── main.py                 # MODIFY: register handler
│   ├── models/
│   │   └── v1_upload.py        # (mungkin tambah helper)
│   └── static/
│       └── js/
│           └── app.js          # REWRITE: ganti SSE → polling, endpoint /api/pinter/
└── tests/
    └── integration/
        └── test_upload.py      # MODIFY: tambah test untuk MISSING_FILE/MISSING_TRX_ID
        └── test_pinter_extract.py # MODIFY: tambah test untuk error format
```

## Phase 0: Research

Lihat [research.md](./research.md) — keputusan teknis sudah dikonsolidasi.

## Phase 1: Design

- [contracts/error-format.md](./contracts/error-format.md) — kontrak error response baru
- [quickstart.md](./quickstart.md) — panduan implementasi singkat

## Phase 2: Implementation Roadmap

Garis besar tahap implementasi:

### Tahap 1 — Backend Exception Handler (independent)

1. Edit `web/main.py`:
   - Import `from fastapi.exceptions import RequestValidationError`
   - Tambah `@app.exception_handler(RequestValidationError)` async function
   - Map field error ke `error_code`:
     - `body.file missing` → `MISSING_FILE`
     - `query.trx_id missing` → `MISSING_TRX_ID`
     - lainnya → `VALIDATION_ERROR`
   - Return `JSONResponse` HTTP 400 dengan format `{ status, message, error_code }`

### Tahap 2 — Frontend Rewrite (independent dari Tahap 1)

1. Rewrite `web/static/js/app.js`:
   - Hapus state `jobId`, `jobToken`, `eventSource`
   - Tambah state `trxId`, `pollTimer`
   - `startVerification()`:
     - `POST /api/pinter/upload` dengan FormData
     - Simpan `trx_id` dari response
     - Mulai polling
   - `pollResult()`:
     - `GET /api/pinter/extract?trx_id=${trxId}`
     - Kalau `status === "progress"` → schedule poll lagi (1.5s)
     - Kalau `status === "success"` → render hasil berdasarkan `data.doc_type`
     - Kalau `status === "fail"` → tampilkan error
   - Rewrite `renderResult()`:
     - Switch `data.doc_type`:
       - `"invoice"` → `renderInvoiceDetail()` (vendor, line_items, dll)
       - `"receipt"` → `renderReceiptDetail()` (merchant, items_purchased, dll)
       - `"unknown"` → `renderUnknownDetail()` (info + authenticity only)
   - Pertahankan `renderAuthenticity()` (struktur sama)

2. Tidak perlu ubah `web/static/index.html` atau `css/` (kecuali ada label hard-coded yang perlu dikoreksi)

### Tahap 3 — Tests (tergantung Tahap 1)

1. Edit `tests/integration/test_upload.py`:
   - Update `test_upload_reject_missing_file` agar assert HTTP 400 + `error_code === "MISSING_FILE"`
2. Edit `tests/integration/test_pinter_extract.py`:
   - Tambah `test_extract_missing_trx_id_returns_400_with_error_code`
3. Pastikan semua test passing (target: ≥ 41 passed)

### Tahap 4 — Dokumentasi (tergantung Tahap 1-3)

1. Update README.md `Error Codes` table — tambah `MISSING_TRX_ID`, `VALIDATION_ERROR`
2. Update `web/API.md` (jika masih dipakai sebagai sumber kebenaran)

### Tahap 5 — Smoke Test Manual End-to-End

1. Jalankan server lokal
2. Buka `http://localhost:8080` di browser
3. Drag PDF → harus berhasil upload, polling, render hasil
4. Test error case via curl:
   - `curl -X POST http://localhost:8080/api/pinter/upload` → 400 + format seragam
   - `curl http://localhost:8080/api/pinter/extract` → 400 + format seragam

## Progress

| Phase | Status |
|-------|--------|
| Spec | ✅ |
| Plan (this file) | ✅ |
| Research | ✅ |
| Contracts | ✅ |
| Quickstart | ✅ |
| Tasks (`/speckit-tasks`) | ⏳ |
| Implementation (`/speckit-implement`) | ⏳ |

## Risiko & Mitigasi

| Risiko | Mitigasi |
|--------|----------|
| Polling membebani server | Interval 1.5s + max 5 menit total (2x AI processing time) |
| Race condition kalau user submit 2x cepat | Disable button selama polling aktif |
| Error format yang sudah pakai HTTP 422 di kode klien lama | Test dengan PISmart sebelum deploy; klien yang baca `detail` tetap dapat info di field `message` |
| FastAPI handler order salah | Register `RequestValidationError` handler SEBELUM mount static |
