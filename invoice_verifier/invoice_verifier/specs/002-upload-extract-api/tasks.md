# Tasks: Upload & Extract Invoice API v1

**Input**: Design documents dari `specs/002-upload-extract-api/`

**Prerequisites**: plan.md ✓ | spec.md ✓ | research.md ✓ | data-model.md ✓ | contracts/api-v1.md ✓

**Tests**: Tidak diminta — tidak ada test tasks yang digenerate.

**Organization**: Tasks dikelompokkan per user story agar setiap story bisa diimplementasi dan ditest secara independen.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Bisa paralel (file berbeda, tidak ada dependensi ke task yang belum selesai)
- **[Story]**: User story yang dituju (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Tambahkan dependency baru dan buat struktur package database.

- [X] T001 Tambahkan `aiosqlite>=0.19.0` ke `requirements.txt`
- [X] T002 [P] Buat `web/db/__init__.py` (file kosong untuk package marker)
- [X] T003 [P] Tambahkan env var `SQLITE_DB_PATH` ke `web/config.py` dengan default `data/invoice_verifier.db`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database layer yang WAJIB selesai sebelum semua user story bisa dimulai.

**⚠️ CRITICAL**: Tidak ada user story yang bisa dimulai sebelum phase ini selesai.

- [X] T004 Buat `web/db/sqlite.py` dengan fungsi: `init_db()` (buat tabel `upload_jobs` jika belum ada), `create_job(trx_id, filename)`, `get_job(trx_id) -> dict | None`, `update_job(trx_id, status, result_json=None, error_message=None)` — gunakan `aiosqlite`, schema sesuai `data-model.md`
- [X] T005 Update `web/main.py` lifespan: panggil `await init_db()` saat startup sebelum menerima request

**Checkpoint**: Database layer siap — user story bisa dimulai.

---

## Phase 3: User Story 1 — Upload PDF dan Terima trx_id (Priority: P1) 🎯 MVP

**Goal**: PISmart dapat mengirim PDF dan langsung mendapat `trx_id` tanpa menunggu ekstraksi selesai.

**Independent Test**: `POST /api/v1/upload` dengan PDF valid → response berisi `trx_id` + `status: "progress"` dalam < 3 detik. Verifikasi row tersimpan di SQLite dengan `status = "progress"`.

### Implementation

- [X] T006 [P] [US1] Buat `web/models/v1_upload.py` dengan model `UploadResponse(trx_id: str, status: str, message: str)`
- [X] T007 [US1] Buat `web/api/v1_upload.py`: buat `router = APIRouter(prefix="/api/v1", tags=["v1"])`, implementasi `POST /upload` — validasi file (ekstensi + magic bytes `%PDF`), generate `trx_id` (UUID4), simpan ke SQLite via `create_job()`, buat job di `AgentRunnerService`, return `UploadResponse`
- [X] T008 [US1] Tambahkan fungsi `run_and_persist(trx_id, runner_service)` di `web/api/v1_upload.py` — jalankan `await runner_service.run_job(trx_id)`, lalu update SQLite: `status: "success"` + `result_json` (serialisasi `job.result`) jika sukses, atau `status: "fail"` + `error_message` jika error
- [X] T009 [US1] Update `web/main.py`: import dan `app.include_router(v1_upload_router)`

**Checkpoint**: US1 selesai dan bisa ditest independen via Postman/curl.

---

## Phase 4: User Story 2 — Polling Hasil Ekstraksi dari Database (Priority: P2)

**Goal**: PISmart dapat mengambil status dan hasil ekstraksi lengkap dari database menggunakan `trx_id`.

**Independent Test**: `GET /api/v1/extract/{trx_id}` dengan `trx_id` valid → response berisi `status` dan `data` (JSON penuh dari agent) sesuai state di database. Test tiga skenario: `progress`, `success`, `fail`.

### Implementation

- [X] T010 [US2] Tambahkan model `ExtractResponse(trx_id: str, status: str, message: str, data: dict | None)` ke `web/models/v1_upload.py`
- [X] T011 [US2] Tambahkan endpoint `GET /extract/{trx_id}` di `web/api/v1_upload.py` — baca dari SQLite via `get_job(trx_id)`, jika tidak ada return 404, parse `result_json` dari kolom TEXT ke dict, return `ExtractResponse` dengan `data` berisi seluruh JSON hasil agent (tidak disaring)

**Checkpoint**: US2 selesai — alur upload → poll → hasil bisa ditest end-to-end.

---

## Phase 5: User Story 3 — Error Response Konsisten (Priority: P3)

**Goal**: Semua error dari kedua endpoint menggunakan format `{ status: "fail", message, error_code }` yang identik.

**Independent Test**: Trigger setiap kondisi error (kirim non-PDF → 400, file > 20MB → 413, `trx_id` tidak ada → 404, simulasi crash → 500) — semua response body mengikuti format yang sama persis.

### Implementation

- [X] T012 [P] [US3] Tambahkan `V1ErrorResponse(status: str = "fail", message: str, error_code: str)` dan exception class `V1ApiError(status_code: int, message: str, error_code: str)` ke `web/models/v1_upload.py`
- [X] T013 [US3] Daftarkan exception handler untuk `V1ApiError` di `web/main.py` — handler mengembalikan `JSONResponse(status_code=exc.status_code, content=V1ErrorResponse(...).model_dump())`
- [X] T014 [US3] Update `POST /api/v1/upload` di `web/api/v1_upload.py`: ganti semua `HTTPException` dengan `raise V1ApiError(...)` menggunakan error codes: `MISSING_FILE` (400), `INVALID_FILE_TYPE` (400), `FILE_TOO_LARGE` (413), `INTERNAL_ERROR` (500)
- [X] T015 [US3] Update `GET /api/v1/extract/{trx_id}` di `web/api/v1_upload.py`: ganti semua `HTTPException` dengan `raise V1ApiError(...)` menggunakan error codes: `TRX_NOT_FOUND` (404), `INTERNAL_ERROR` (500)

**Checkpoint**: Semua US selesai — semua error response konsisten.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T016 [P] Update `web/API.md`: tambahkan section "API v1 (PISmart Integration)" dengan dokumentasi `POST /api/v1/upload` dan `GET /api/v1/extract/{trx_id}` sesuai `contracts/api-v1.md`
- [X] T017 Update `baca_invoice/.env_example`: tambahkan `SQLITE_DB_PATH=data/invoice_verifier.db`
- [ ] T018 Smoke test manual: jalankan server, upload PDF invoice dari folder `input/`, poll result sampai `status: success`, verifikasi row di SQLite menggunakan `sqlite3 data/invoice_verifier.db "SELECT trx_id, status, length(result_json) FROM upload_jobs;"`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Tidak ada dependensi — mulai langsung. T002 dan T003 paralel.
- **Foundational (Phase 2)**: Menunggu T001 (requirements) — BLOCKS semua user story
- **US1 (Phase 3)**: Menunggu Phase 2 selesai. T006 paralel dengan T007.
- **US2 (Phase 4)**: Menunggu T007 dan T008 (upload endpoint + background runner harus ada dulu)
- **US3 (Phase 5)**: Bisa dimulai setelah T006 (models sudah ada). T012 paralel dengan T013.
- **Polish (Phase 6)**: Menunggu semua US selesai

### User Story Dependencies

- **US1 (P1)**: Bebas setelah Phase 2 — tidak ada dependensi ke US lain
- **US2 (P2)**: Bergantung pada US1 (perlu `run_and_persist` dan job runner sudah berjalan)
- **US3 (P3)**: Independen dari US2, bisa dimulai bersamaan setelah T006 selesai

### Parallel Opportunities

```
Phase 1 paralel: T002 || T003
Phase 3 paralel: T006 || T007 (mulai T006 dulu, T007 setelah T004 selesai)
Phase 5 paralel: T012 || T013
Phase 6 paralel: T016 || T017
```

---

## Implementation Strategy

### MVP (US1 saja)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T005)
3. Phase 3: US1 (T006–T009)
4. **STOP & VALIDATE**: Test upload PDF → terima `trx_id` → verifikasi DB

### Full Implementation

1. Setup + Foundational
2. US1 → smoke test
3. US2 → smoke test end-to-end
4. US3 → verifikasi semua error format
5. Polish + dokumentasi

---

## Notes

- Tidak ada test tasks (tidak diminta di spec)
- `result_json` di SQLite disimpan sebagai TEXT (JSON string) — parse dengan `json.loads()` saat dibaca
- `V1ApiError` hanya untuk prefix `/api/v1/` — tidak mengganggu error handler existing di `/api/travel/` dan `/api/verify/`
- File PDF tetap di `UPLOAD_DIR/{trx_id}/` setelah job selesai (cleanup mengikuti eviction existing)
