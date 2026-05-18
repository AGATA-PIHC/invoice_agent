# Research: Upload & Extract Invoice API v1

**Generated**: 2026-05-18
**Feature**: 002-upload-extract-api

## Decision 1: Database — SQLite dengan kolom JSON

**Decision**: Gunakan SQLite via modul `sqlite3` bawaan Python (tanpa ORM). Satu tabel `upload_jobs` dengan kolom `result_json TEXT` untuk menyimpan hasil ekstraksi secara fleksibel.

**Rationale**:
- SQLite built-in Python — zero dependency tambahan
- Kolom `TEXT` untuk JSON cukup: SQLite 3.38+ mendukung fungsi `json_extract()` jika diperlukan query ke dalam JSON di masa depan
- Tidak perlu migrasi schema saat AI agent menambah field baru ke output
- Sesuai dengan keputusan user: SQLite sementara, bisa diganti PostgreSQL later

**Alternatives considered**:
- SQLAlchemy ORM: overhead terlalu besar untuk use case sederhana ini
- TinyDB / JSON file: tidak support concurrent writes dengan baik
- In-memory (existing pattern): ditolak karena user menginginkan persistensi

---

## Decision 2: Async SQLite — aiosqlite

**Decision**: Gunakan `aiosqlite` untuk operasi database non-blocking agar tidak memblokir event loop FastAPI.

**Rationale**:
- FastAPI berjalan di asyncio — blocking `sqlite3` calls di endpoint akan freeze event loop
- `aiosqlite` adalah thin async wrapper di atas `sqlite3` bawaan, overhead minimal
- API identik dengan `sqlite3` — mudah di-swap ke asyncpg (PostgreSQL) di masa depan

**Alternatives considered**:
- `sqlite3` synchronous di `run_in_executor`: lebih kompleks, thread pool overhead
- `databases` library: overkill, tambahkan SQLAlchemy Core dependency

**Dependency baru yang perlu ditambahkan**: `aiosqlite>=0.19.0`

---

## Decision 3: Router prefix — `/api/v1/`

**Decision**: Buat router baru `web/api/v1_upload.py` dengan prefix `/api/v1` dan tag `v1`.

**Rationale**:
- Memisahkan dari endpoint existing (`/api/travel/`, `/api/verify/`) yang tidak menggunakan versioning
- Prefix `v1` membuka jalur untuk upgrade tanpa breaking change di masa depan
- File terpisah menjaga ukuran file tetap manageable

---

## Decision 4: Error response format

**Decision**: Gunakan Pydantic model `ErrorDetail` yang di-raise via custom exception handler. Format: `{ "status": "fail", "message": str, "error_code": str }`.

**Rationale**:
- FastAPI exception handler terpusat memastikan format konsisten — tidak ada risiko satu endpoint miss
- `error_code` sebagai string constant (bukan integer) lebih mudah dibaca PISmart
- Tidak mengganti error handler existing (untuk `/api/verify/` dan `/api/travel/`) — handler baru khusus untuk prefix `/api/v1/`

**Error codes yang didefinisikan**:
| error_code | HTTP | Kondisi |
|---|---|---|
| `MISSING_FILE` | 400 | Field `file` tidak ada di request |
| `INVALID_FILE_TYPE` | 400 | File bukan PDF |
| `FILE_TOO_LARGE` | 413 | Ukuran melebihi batas |
| `TRX_NOT_FOUND` | 404 | `trx_id` tidak ada di database |
| `INTERNAL_ERROR` | 500 | Error tak terduga |

---

## Decision 5: Background processing — reuse AgentRunnerService

**Decision**: Reuse `AgentRunnerService` yang sudah ada untuk menjalankan ekstraksi. Tambahkan callback/hook untuk menulis hasil ke SQLite setelah job selesai.

**Rationale**:
- `AgentRunnerService` sudah teruji dan mengelola concurrency limit
- Menghindari duplikasi logika background job
- Callback pattern: setelah `run_job()` selesai, tulis result ke SQLite sebelum return

**Pola integrasi**:
```
POST /api/v1/upload
  → simpan ke SQLite (status: progress)
  → AgentRunnerService.create_job(trx_id, ...)
  → asyncio.create_task(run_and_persist(trx_id))
    → AgentRunnerService.run_job(trx_id)
    → update SQLite (status: success/fail, result_json)
```

---

## Decision 6: File storage — direktori existing UPLOAD_DIR

**Decision**: Gunakan `UPLOAD_DIR` yang sudah dikonfigurasi di `web/config.py` (`tmp_uploads/`). Subfolder per `trx_id` seperti pola existing.

**Rationale**: Konsisten dengan `/api/travel/submit` — tidak perlu konfigurasi baru.

**Catatan**: File PDF tetap di disk selama job ada. Cleanup melalui `eviction_loop` yang sudah berjalan di `AgentRunnerService` (jika job di-evict, folder perlu ikut dihapus).
