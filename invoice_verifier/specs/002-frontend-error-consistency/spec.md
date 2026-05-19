# Feature Spec: Frontend & Error Response Consistency

**Branch**: `003-frontend-error-consistency` (proposed)
**Date**: 2026-05-18
**Status**: Draft

## Latar Belakang

Setelah konsolidasi API ke PINTER-only (spec 001), ditemukan dua inkonsistensi:

1. **Frontend rusak** — `web/static/js/app.js` masih memanggil endpoint lama `/api/verify/upload` dan SSE `/api/verify/{job_id}/stream` yang sudah dihapus. UI di-mount di root `/` oleh FastAPI (`web/main.py:89`), jadi user yang membuka browser ke `http://localhost:8080` mendapat UI yang gagal upload.

2. **Error 422 tidak seragam** — Backend tidak punya handler untuk `RequestValidationError`. Request tanpa file ke `/api/pinter/upload` atau tanpa `trx_id` ke `/api/pinter/extract` mendapat response 422 default FastAPI (`{"detail": [...]}`) — bukan format `{ status, message, error_code }` yang dipakai endpoint lain.

## User Stories

### US-1: User upload via web UI
**Sebagai** user yang membuka `http://localhost:8080`,
**saya ingin** drag-and-drop PDF dan melihat hasil ekstraksi otomatis,
**sehingga** saya tidak perlu memakai curl untuk testing.

**Acceptance**:
- Klik / drop PDF → upload sukses, dapat `trx_id`
- UI menampilkan status "memproses" sambil polling
- Setelah selesai, render hasil sesuai `doc_type`:
  - `invoice` → tampilkan field invoice (vendor, line_items, dll)
  - `receipt` → tampilkan field receipt (merchant, items_purchased, dll)
  - `unknown` → tampilkan pesan "Dokumen tidak terklasifikasi" + authenticity
- Saat fail → tampilkan `error_code` + `message`

### US-2: Konsumen API dapat error format seragam
**Sebagai** developer PISmart yang integrasi,
**saya ingin** semua error response punya struktur `{ status, message, error_code }`,
**sehingga** parsing error di sisi klien konsisten.

**Acceptance**:
- `POST /api/pinter/upload` tanpa file → `400 { status: "fail", message: "...", error_code: "MISSING_FILE" }`
- `GET /api/pinter/extract` tanpa `trx_id` → `400 { ..., error_code: "MISSING_TRX_ID" }`
- Field validation error generic lain → `400 { ..., error_code: "VALIDATION_ERROR" }`

## Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Frontend memanggil `POST /api/pinter/upload` (bukan `/api/verify/upload`) | High |
| FR-2 | Frontend polling `GET /api/pinter/extract?trx_id=...` (bukan SSE) menggunakan interval 1-2 detik | High |
| FR-3 | Frontend membedakan render output berdasarkan `data.doc_type` | High |
| FR-4 | Frontend menampilkan pesan informatif untuk `doc_type: "unknown"` | Medium |
| FR-5 | Backend menangkap `RequestValidationError` dan mengembalikan format `{ status, message, error_code }` | High |
| FR-6 | Error code untuk missing file = `MISSING_FILE`, missing trx_id = `MISSING_TRX_ID`, lainnya = `VALIDATION_ERROR` | High |
| FR-7 | HTTP status code untuk validation error = 400 (bukan 422 default FastAPI) | Medium |
| FR-8 | Tidak ada breaking change pada endpoint `/api/pinter/*` yang sudah ada | High |

## Success Criteria

- User dapat upload PDF via UI dan melihat hasil ekstraksi tanpa error console
- Test integration baru untuk error validation pass
- `curl -X POST /api/pinter/upload` (no file) → response berformat seragam, HTTP 400
- README `Error Codes` table di-update menambahkan `MISSING_TRX_ID` dan `VALIDATION_ERROR`

## Non-Goals

- Tidak menambah endpoint baru
- Tidak mengubah skema `data` di response success
- Tidak menggunakan WebSocket atau SSE
- Tidak melakukan rebrand UI

## Assumptions

- Polling interval 1.5 detik cukup responsif untuk UX (ekstraksi AI biasanya 10-30 detik)
- User memakai browser modern (ES2020+, async/await native)
- Static files akan tetap di-serve oleh FastAPI (bukan dari CDN terpisah)
