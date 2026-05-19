# Feature Specification: Upload & Extract Invoice API v1

> **⚠️ STATUS: SUPERSEDED (2026-05-19)**
>
> Spec ini menyebut endpoint `/api/v1/upload` dan `/api/v1/extract/{trx_id}` yang **TIDAK PERNAH** diimplementasikan dengan prefix tersebut. Implementasi final memakai prefix `/api/pinter/`:
> - `POST /api/v1/upload` → **`POST /api/pinter/upload`**
> - `GET /api/v1/extract/{trx_id}` → **`GET /api/pinter/extract?trx_id={trx_id}`** (query param, bukan path param)
>
> Sumber kebenaran aktif:
> - [`README.md`](../../../README.md) (root invoice_verifier)
> - [`web/API.md`](../../../web/API.md) — API reference lengkap
> - [`specs/002-frontend-error-consistency/`](../../../specs/002-frontend-error-consistency/) — spec aktif terkini
>
> Spec ini dipertahankan sebagai catatan historis perancangan awal. **Jangan jadikan rujukan untuk integrasi PISmart.**

---

**Feature Branch**: `002-upload-extract-api`

**Created**: 2026-05-18

**Status**: ~~Draft~~ **SUPERSEDED**

**Input**: Endpoint POST /api/v1/upload dan GET /api/v1/extract/{trx_id} untuk integrasi PISmart → PINTER secara asynchronous.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload PDF dan Terima trx_id (Priority: P1)

PISmart mengirim file PDF invoice/receipt ke PINTER melalui HTTP multipart upload. PINTER langsung
mengembalikan `trx_id` sebagai tanda terima, menyimpan record job ke database, sementara proses
ekstraksi berjalan di background. Setelah ekstraksi selesai, hasilnya ditulis ke database.

**Why this priority**: Ini adalah entry point utama integrasi. Tanpa upload yang berhasil, seluruh
alur tidak bisa dimulai.

**Independent Test**: Dapat diuji dengan mengirim PDF valid ke endpoint dan memverifikasi bahwa
`trx_id` diterima dalam response dengan `status: progress`.

**Acceptance Scenarios**:

1. **Given** PISmart memiliki file PDF invoice yang valid, **When** mengirim POST ke `/api/v1/upload`
   dengan `multipart/form-data` field `file`, **Then** PINTER mengembalikan `200 OK` dengan body
   `{ trx_id, status: "progress", message }`.
2. **Given** PISmart mengirim file bukan PDF (e.g., `.docx`), **When** POST ke `/api/v1/upload`,
   **Then** PINTER mengembalikan `400 Bad Request` dengan `{ status: "fail", message, error_code: "INVALID_FILE_TYPE" }`.
3. **Given** PISmart mengirim file PDF melebihi batas ukuran, **When** POST ke `/api/v1/upload`,
   **Then** PINTER mengembalikan `413 Payload Too Large` dengan `{ status: "fail", message, error_code: "FILE_TOO_LARGE" }`.
4. **Given** PISmart mengirim request tanpa field `file`, **When** POST ke `/api/v1/upload`,
   **Then** PINTER mengembalikan `400 Bad Request` dengan `{ status: "fail", message, error_code: "MISSING_FILE" }`.

---

### User Story 2 - Polling Hasil Ekstraksi dari Database (Priority: P2)

Setelah mendapat `trx_id`, PISmart melakukan polling ke endpoint GET. PINTER membaca status dan
hasil ekstraksi dari database berdasarkan `trx_id`, lalu mengembalikannya. Karena hasil disimpan
di database, data tetap tersedia meskipun server di-restart.

**Why this priority**: Polling adalah cara PISmart mengambil hasil. Tanpa ini, `trx_id` tidak
berguna.

**Independent Test**: Dapat diuji dengan `trx_id` valid yang sudah selesai diproses, memverifikasi
bahwa response mengandung `status: success` dan field `data` berisi data invoice.

**Acceptance Scenarios**:

1. **Given** ekstraksi masih berjalan, **When** GET `/api/v1/extract/{trx_id}`, **Then** PINTER
   mengembalikan `{ trx_id, status: "progress", message, data: null }`.
2. **Given** ekstraksi selesai berhasil, **When** GET `/api/v1/extract/{trx_id}`, **Then** PINTER
   mengembalikan `{ trx_id, status: "success", message, data: { invoice_number, date, vendor_name, items, total_amount, currency, ... } }`.
3. **Given** ekstraksi gagal (PDF tidak terbaca / konten tidak dikenali), **When** GET
   `/api/v1/extract/{trx_id}`, **Then** PINTER mengembalikan `{ trx_id, status: "fail", message, data: null }`.
4. **Given** `trx_id` tidak dikenal, **When** GET `/api/v1/extract/{trx_id}`, **Then** PINTER
   mengembalikan `404 Not Found` dengan `{ status: "fail", message, error_code: "TRX_NOT_FOUND" }`.

---

### User Story 3 - Error Response Konsisten (Priority: P3)

Semua kondisi error dari kedua endpoint mengikuti format body yang seragam sehingga PISmart dapat
menangani error secara generik tanpa perlu logika parsing per-endpoint.

**Why this priority**: Konsistensi error mempermudah integrasi di sisi PISmart. Tanpa ini,
integrasi masih bisa berjalan tapi error handling lebih fragile.

**Independent Test**: Dapat diuji dengan memicu setiap jenis error (400, 404, 413, 500) dan
memverifikasi bahwa seluruh response mengikuti format `{ status: "fail", message, error_code }`.

**Acceptance Scenarios**:

1. **Given** error apapun terjadi, **When** PINTER mengembalikan error response, **Then** body
   selalu mengandung `status: "fail"`, `message` (human-readable), dan `error_code` (machine-readable).
2. **Given** error internal server (500), **When** terjadi kegagalan tak terduga, **Then** PINTER
   mengembalikan `500` dengan `error_code: "INTERNAL_ERROR"` tanpa mengekspos detail teknis.

---

### Edge Cases

- Apa yang terjadi jika file PDF valid secara format tapi isinya kosong atau bukan invoice?
- Bagaimana jika dua request upload dengan file yang sama dikirim bersamaan?
- Apa yang terjadi jika PISmart polling `trx_id` yang sudah expired / dibersihkan dari memory?
- Bagaimana jika PDF mengandung multiple pages dengan konten campuran?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistem HARUS menyediakan endpoint `POST /api/v1/upload` yang menerima file PDF via `multipart/form-data` dengan field bernama `file`.
- **FR-002**: Endpoint upload HARUS menyimpan record job (dengan `trx_id`, `status: "progress"`, dan metadata file) ke database sebelum mengembalikan response.
- **FR-003**: Endpoint upload HARUS mengembalikan `trx_id` (unique identifier) dan `status: "progress"` secara sinkron, tanpa menunggu proses ekstraksi selesai.
- **FR-004**: Sistem HARUS menjalankan proses ekstraksi invoice di background setelah upload berhasil, dan menulis hasil ekstraksi ke database saat selesai.
- **FR-005**: Sistem HARUS menyediakan endpoint `GET /api/v1/extract/{trx_id}` yang membaca status dan hasil ekstraksi dari database berdasarkan `trx_id`.
- **FR-006**: Endpoint extract HARUS mengembalikan `status` dengan tiga nilai valid: `progress` (sedang diproses), `success` (selesai berhasil), `fail` (gagal).
- **FR-007**: Endpoint extract HARUS mengembalikan field `data` berisi objek hasil ekstraksi invoice saat `status: "success"`, dan `null` saat status lain.
- **FR-008**: Field `data` pada hasil ekstraksi HARUS mengembalikan **seluruh field JSON** yang berhasil diekstrak oleh AI agent — tidak ada field yang dihilangkan atau disaring.
- **FR-009**: Data hasil ekstraksi yang tersimpan di database HARUS bisa diambil kembali oleh PISmart bahkan setelah server restart.
- **FR-010**: Kedua endpoint HARUS mengembalikan error response dengan format konsisten: `{ status: "fail", message, error_code }`.
- **FR-011**: Sistem HARUS menolak file yang bukan PDF dengan HTTP `400` dan `error_code: "INVALID_FILE_TYPE"`.
- **FR-012**: Sistem HARUS menolak file melebihi batas ukuran maksimum dengan HTTP `413` dan `error_code: "FILE_TOO_LARGE"`.
- **FR-013**: Endpoint extract HARUS mengembalikan HTTP `404` dengan `error_code: "TRX_NOT_FOUND"` jika `trx_id` tidak ditemukan di database.
- **FR-014**: Error internal server HARUS mengembalikan HTTP `500` dengan `error_code: "INTERNAL_ERROR"` tanpa mengekspos detail teknis ke klien.

### Key Entities

- **Upload Job** *(disimpan di SQLite)*: Representasi satu sesi upload-ekstraksi. Memiliki `trx_id` (primary key), `status` (`progress`/`success`/`fail`), `created_at`, `updated_at`, nama file asli, dan seluruh hasil ekstraksi tersimpan sebagai kolom JSON.
- **ExtractedInvoice**: Seluruh objek JSON hasil ekstraksi AI agent, dikembalikan utuh ke PISmart tanpa disaring. Struktur mengikuti output agent yang sudah ada (`FlightTicketResult` atau `HotelInvoiceResult`).
- **ErrorResponse**: Format error seragam yang dikembalikan ke klien. Memiliki `status: "fail"`, `message` (human-readable), `error_code` (machine-readable constant).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: PISmart dapat menyelesaikan alur upload hingga terima `trx_id` dalam waktu kurang dari 3 detik untuk file PDF berukuran hingga 10 MB.
- **SC-002**: PISmart dapat mengambil hasil ekstraksi yang lengkap melalui polling dalam waktu rata-rata kurang dari 30 detik setelah upload.
- **SC-003**: Seluruh kondisi error (400, 404, 413, 500) mengembalikan response dengan format yang identik sehingga PISmart dapat menangani error dengan satu handler generik.
- **SC-004**: Sistem mampu memproses minimal 10 upload bersamaan tanpa ada request yang gagal akibat bottleneck internal.
- **SC-005**: 100% error response mengandung `status`, `message`, dan `error_code` — tidak ada error yang mengembalikan body HTML atau body kosong.

## Assumptions

- File PDF yang dikirim PISmart berisi dokumen invoice atau receipt berbahasa Indonesia atau Inggris.
- Ukuran file maksimum mengikuti konfigurasi yang sudah ada di sistem (default 20 MB).
- Tidak ada autentikasi tambahan yang diperlukan untuk API v1 ini (berbeda dari `/api/travel` yang menggunakan API Key) — dapat dikonfigurasi terpisah jika diperlukan.
- **`trx_id` dan hasilnya disimpan persisten di database** sehingga tetap tersedia meski server restart — ini berbeda dari endpoint `/api/travel/` yang menggunakan in-memory store.
- **Database yang digunakan adalah SQLite** — dipilih untuk kesederhanaan dan tidak memerlukan setup server terpisah.
- Kolom JSON di SQLite digunakan untuk menyimpan seluruh hasil ekstraksi secara fleksibel, sehingga tidak perlu migrasi schema saat field baru ditambahkan.
- Sistem yang sudah ada (`AgentRunnerService`) akan digunakan ulang untuk menjalankan ekstraksi di background; hasilnya kemudian ditulis ke SQLite.
- Prefix `/api/v1/` digunakan untuk membedakan dari endpoint existing (`/api/travel/`, `/api/verify/`).
- Jika `trx_id` yang diminta sudah ada di database (misalnya request duplikat), sistem mengembalikan data yang sudah ada tanpa memproses ulang.
