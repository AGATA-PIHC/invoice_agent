# Data Model: Upload & Extract Invoice API v1

**Feature**: 002-upload-extract-api
**Database**: SQLite

---

## Tabel: `upload_jobs`

Satu tabel tunggal untuk menyimpan seluruh lifecycle upload-ekstraksi.

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| `trx_id` | TEXT | PRIMARY KEY | UUID v4, dibuat saat upload |
| `status` | TEXT | NOT NULL | Enum: `progress` / `success` / `fail` |
| `filename` | TEXT | NOT NULL | Nama file PDF asli yang diupload |
| `created_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp saat upload |
| `updated_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp terakhir update |
| `result_json` | TEXT | NULLABLE | Seluruh output JSON dari AI agent (FlightTicketResult / HotelInvoiceResult). NULL saat status `progress`. |
| `error_message` | TEXT | NULLABLE | Pesan error jika status `fail`. NULL jika berhasil. |

### DDL

```sql
CREATE TABLE IF NOT EXISTS upload_jobs (
    trx_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'progress',
    filename     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    result_json  TEXT,
    error_message TEXT
);
```

### Index

```sql
-- Untuk query by status (opsional, jika diperlukan monitoring/dashboard)
CREATE INDEX IF NOT EXISTS idx_upload_jobs_status ON upload_jobs(status);
```

---

## State Transitions

```
[upload] → progress
              ↓
    [ekstraksi selesai berhasil] → success
              ↓
    [ekstraksi gagal]            → fail
```

- Dari `progress` hanya bisa ke `success` atau `fail`
- Tidak ada state kembali ke `progress` setelah selesai

---

## File Lokasi Database

```
{UPLOAD_DIR}/../invoice_verifier.db
```
atau dikonfigurasi via env var `SQLITE_DB_PATH` (default: `data/invoice_verifier.db` di project root).
