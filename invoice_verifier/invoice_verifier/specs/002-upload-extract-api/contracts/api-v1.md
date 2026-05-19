# API Contract: Upload & Extract Invoice v1

**Prefix**: `/api/v1`
**Auth**: Tidak diperlukan (dapat dikonfigurasi via env var di masa depan)
**Content-Type response**: `application/json`

---

## POST /api/v1/upload

Upload file PDF invoice untuk diekstraksi.

### Request

```
Content-Type: multipart/form-data
```

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `file` | File (PDF) | Ya | File PDF invoice/receipt, maks 20 MB |

### Response 200 — Upload diterima

```json
{
  "trx_id": "9f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "progress",
  "message": "Dokumen diterima dan sedang diproses."
}
```

### Error Responses

**400 — File tidak ada**
```json
{
  "status": "fail",
  "message": "Field 'file' wajib diisi.",
  "error_code": "MISSING_FILE"
}
```

**400 — Bukan PDF**
```json
{
  "status": "fail",
  "message": "File harus berformat PDF.",
  "error_code": "INVALID_FILE_TYPE"
}
```

**413 — File terlalu besar**
```json
{
  "status": "fail",
  "message": "Ukuran file melebihi batas maksimum 20 MB.",
  "error_code": "FILE_TOO_LARGE"
}
```

**500 — Internal error**
```json
{
  "status": "fail",
  "message": "Terjadi kesalahan internal. Silakan coba lagi.",
  "error_code": "INTERNAL_ERROR"
}
```

---

## GET /api/v1/extract/{trx_id}

Ambil status dan hasil ekstraksi berdasarkan `trx_id`.

### Request

| Parameter | Lokasi | Tipe | Keterangan |
|---|---|---|---|
| `trx_id` | path | string (UUID) | ID transaksi dari response POST /upload |

### Response 200 — Masih diproses

```json
{
  "trx_id": "9f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "progress",
  "message": "Dokumen sedang diproses.",
  "data": null
}
```

### Response 200 — Selesai berhasil

```json
{
  "trx_id": "9f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "receipt_number": "INV-2026-001",
    "booking_date": "2026-05-10",
    "traveler_name": "Budi Santoso",
    "airline": "Garuda Indonesia",
    "route_from": "CGK",
    "route_to": "DPS",
    "flight_date": "2026-05-15",
    "total_payment": 1250000,
    "currency": "IDR",
    "authenticity": {
      "verdict": "AUTENTIK",
      "confidence_score": 0.92
    },
    "extraction_confidence": 0.88,
    "...": "seluruh field JSON dari agent dikembalikan utuh"
  }
}
```

### Response 200 — Gagal

```json
{
  "trx_id": "9f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "status": "fail",
  "message": "Ekstraksi gagal: dokumen tidak dapat dibaca.",
  "data": null
}
```

### Error Responses

**404 — trx_id tidak ditemukan**
```json
{
  "status": "fail",
  "message": "Transaction ID tidak ditemukan.",
  "error_code": "TRX_NOT_FOUND"
}
```

**500 — Internal error**
```json
{
  "status": "fail",
  "message": "Terjadi kesalahan internal.",
  "error_code": "INTERNAL_ERROR"
}
```

---

## Pola Polling yang Disarankan

```
POST /api/v1/upload → terima trx_id
LOOP:
  GET /api/v1/extract/{trx_id}
  IF status == "progress" → tunggu 3-5 detik, ulangi
  IF status == "success"  → ambil data, selesai
  IF status == "fail"     → tangani error, selesai
```
