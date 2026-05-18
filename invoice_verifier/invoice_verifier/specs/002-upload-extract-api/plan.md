# Implementation Plan: Upload & Extract Invoice API v1

> **⚠️ SUPERSEDED (2026-05-19)** — Endpoint final memakai prefix `/api/pinter/`, bukan `/api/v1/`. Lihat [spec.md](./spec.md) untuk detail. Sumber kebenaran aktif: [`README.md`](../../../README.md) dan [`web/API.md`](../../../web/API.md).

**Branch**: `002-upload-extract-api` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

## Summary

Menambahkan dua endpoint baru (`POST /api/v1/upload` dan `GET /api/v1/extract/{trx_id}`) untuk
integrasi PISmart → PINTER. Berbeda dari endpoint existing, hasil ekstraksi disimpan persisten di
SQLite sehingga tersedia meski server restart. Background processing menggunakan `AgentRunnerService`
yang sudah ada, dengan tambahan layer persistensi ke database.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI, aiosqlite (baru), python-multipart (existing), AgentRunnerService (existing)

**Storage**: SQLite via `aiosqlite` — tabel `upload_jobs` dengan kolom JSON untuk hasil ekstraksi

**Testing**: pytest (manual smoke test via curl/Postman untuk fase ini)

**Target Platform**: Linux/Windows server (same as existing)

**Project Type**: Web service — tambahan endpoint pada aplikasi FastAPI existing

**Performance Goals**: Upload + return trx_id < 3 detik; ekstraksi selesai rata-rata < 30 detik

**Constraints**: File maks 20 MB (existing config); tidak ada auth tambahan di v1

**Scale/Scope**: Same as existing — single process, tidak horizontal scaling

## Constitution Check

Constitution belum diisi (masih template). Tidak ada gate yang dilanggar. Prinsip yang diterapkan:
- Simplicity: SQLite tanpa ORM, langsung `aiosqlite`
- Reuse: `AgentRunnerService` dipakai ulang
- No breaking change: endpoint baru di prefix `/api/v1/`, tidak menyentuh existing

## Project Structure

### Documentation (this feature)

```text
specs/002-upload-extract-api/
├── plan.md              ← file ini
├── research.md          ← keputusan teknis
├── data-model.md        ← schema SQLite
├── contracts/
│   └── api-v1.md        ← API contract lengkap
└── tasks.md             ← dibuat oleh /speckit-tasks
```

### Source Code (repository root)

```text
web/
├── api/
│   └── v1_upload.py         ← NEW: router POST /upload + GET /extract
├── models/
│   └── v1_upload.py         ← NEW: Pydantic request/response models
├── db/
│   ├── __init__.py          ← NEW: db package
│   └── sqlite.py            ← NEW: koneksi + CRUD operasi upload_jobs
├── config.py                ← UPDATE: tambah SQLITE_DB_PATH env var
└── main.py                  ← UPDATE: include v1_upload router

requirements.txt             ← UPDATE: tambah aiosqlite>=0.19.0
```

## Implementation Phases

### Phase 1: Database Layer

Buat `web/db/sqlite.py` — koneksi aiosqlite dan operasi CRUD untuk tabel `upload_jobs`.

**Deliverables**:
- `web/db/__init__.py`
- `web/db/sqlite.py` dengan fungsi: `init_db()`, `create_job()`, `update_job()`, `get_job()`
- `web/config.py` diupdate dengan `SQLITE_DB_PATH`
- `web/main.py` diupdate panggil `init_db()` di lifespan

### Phase 2: Models & Error Handler

Buat Pydantic models dan error handler konsisten untuk `/api/v1/`.

**Deliverables**:
- `web/models/v1_upload.py` dengan: `UploadResponse`, `ExtractResponse`, `V1ErrorResponse`
- Exception handler untuk `V1ApiError` didaftarkan di `main.py` (hanya untuk prefix `/api/v1/`)

### Phase 3: Endpoint Implementation

Buat router `web/api/v1_upload.py` dengan kedua endpoint.

**Deliverables**:
- `POST /api/v1/upload` — validasi PDF, simpan ke DB, kick background job
- `GET /api/v1/extract/{trx_id}` — baca dari DB, return full JSON result
- Background runner `run_and_persist()` — wrap `AgentRunnerService.run_job()` + update DB
- Router diinclude di `web/main.py`

### Phase 4: Dependency & Smoke Test

Update dependencies dan verifikasi end-to-end.

**Deliverables**:
- `requirements.txt` diupdate: `aiosqlite>=0.19.0`
- Smoke test manual: upload PDF dummy → poll result → verifikasi JSON tersimpan di SQLite
- Verifikasi error responses (400, 404, 413, 500) menggunakan format konsisten
