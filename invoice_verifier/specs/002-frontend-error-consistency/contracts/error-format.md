# Contract: Unified Error Response Format

**Scope**: Semua endpoint `/api/pinter/*` dan validation error.
**Status**: **Non-breaking enhancement** — hanya menambah handler, tidak mengubah struktur response yang sudah ada.

## Format Baku

```json
{
  "status": "fail",
  "message": "<pesan informatif dalam Bahasa Indonesia>",
  "error_code": "<MACHINE_READABLE_CODE>"
}
```

HTTP status code: sesuai jenis error (lihat tabel di bawah).

## Daftar Error Code

| Code | HTTP | Trigger | Pesan default |
|------|------|---------|---------------|
| `MISSING_FILE` | 400 | `POST /api/pinter/upload` tanpa field `file` | "File PDF wajib diisi." |
| `INVALID_FILE_TYPE` | 400 | File bukan PDF (ekstensi/magic bytes) | "File harus berformat PDF." |
| `FILE_TOO_LARGE` | 413 | File melebihi `MAX_UPLOAD_MB` | "Ukuran file melebihi batas maksimum {N} MB." |
| `RATE_LIMITED` | 429 | > 10 upload per IP per menit | "Terlalu banyak permintaan. Coba lagi dalam 1 menit." |
| `MISSING_TRX_ID` | **400** (BARU) | `GET /api/pinter/extract` tanpa query `trx_id` | "Parameter trx_id wajib diisi." |
| `VALIDATION_ERROR` | **400** (BARU) | Field validation error lainnya | (pesan dari Pydantic, di-translate) |
| `TRX_NOT_FOUND` | 404 | trx_id tidak ada di DB | "Transaction ID tidak ditemukan." |
| `TRX_EXPIRED` | 410 | trx_id sudah > `PINTER_TRX_TTL_DAYS` | "Transaction ID sudah kedaluwarsa." |
| `INTERNAL_ERROR` | 500 | Server error tak terduga | "Terjadi kesalahan internal." |
| `UNAUTHORIZED` | 401 | X-API-Key salah/tidak ada | "X-API-Key tidak valid atau tidak ada." |

## Perubahan Eksplisit

### Sebelum

Request: `POST /api/pinter/upload` tanpa file
Response: `422 Unprocessable Entity`
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "file"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

### Sesudah

Request: `POST /api/pinter/upload` tanpa file
Response: `400 Bad Request`
```json
{
  "status": "fail",
  "message": "File PDF wajib diisi.",
  "error_code": "MISSING_FILE"
}
```

### Sebelum

Request: `GET /api/pinter/extract` (tanpa query trx_id)
Response: `422 Unprocessable Entity`
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "trx_id"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

### Sesudah

Request: `GET /api/pinter/extract`
Response: `400 Bad Request`
```json
{
  "status": "fail",
  "message": "Parameter trx_id wajib diisi.",
  "error_code": "MISSING_TRX_ID"
}
```

## Migration Notes untuk PISmart

- Klien lama yang baca `detail` array TIDAK akan crash, tapi tidak akan dapat informasi error → harus migrasi
- Klien baru CUKUP baca `error_code` untuk branching, `message` untuk display ke user
- HTTP code berubah 422 → 400 untuk validation error (hanya 2 kasus di atas)

## Versioning

Tidak diversion-kan. Alasan:
- Format response untuk error path sudah konsisten dengan endpoint lain
- HTTP code mismatch di response 422 dianggap **bug fix**, bukan breaking change
- Komunikasi ke PISmart tetap perlu dilakukan
