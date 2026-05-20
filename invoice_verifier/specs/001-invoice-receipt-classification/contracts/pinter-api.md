# API Contract: PINTER Endpoints (Post Invoice/Receipt Classification)

**Endpoints yang terdampak**: `POST /api/pinter/upload`, `GET /api/pinter/extract`
**Status perubahan**: **Non-breaking** — hanya struktur `data` di `/extract` yang berubah; envelope tetap.

## 1. POST `/api/pinter/upload`

### Request
Tidak berubah. Multipart `file` (PDF, max 20 MB).

### Response 200 — Happy path

Sama seperti sebelumnya:

```json
{
  "trx_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "progress",
  "message": "Dokumen diterima dan sedang diproses."
}
```

### Response 200 — Doc type unknown (BARU)

Pesan disesuaikan agar PISmart tahu sejak awal:

```json
{
  "trx_id": "550e8400-...",
  "status": "progress",
  "message": "Dokumen diterima. Tidak dikenali sebagai invoice/receipt — akan dikembalikan dengan doc_type='unknown'."
}
```

### Error responses

Tidak berubah. **Catatan penting**: tidak ada lagi rejection berdasarkan jenis dokumen — kalau bukan invoice/receipt, **tetap 200**, bukan 400/422.

## 2. GET `/api/pinter/extract?trx_id={trx_id}`

### Response 200 — `data` untuk Invoice

```json
{
  "trx_id": "550e8400-...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "invoice",
    "invoice_number": "INV-2026/001",
    "issue_date": "2026-05-10",
    "due_date": "2026-06-10",
    "vendor_name": "PT Hotel Indah",
    "vendor_address": "Jl. Sudirman 1, Jakarta",
    "vendor_npwp": "01.234.567.8-901.000",
    "vendor_phone": "021-1234567",
    "vendor_email": "billing@hotelindah.id",
    "buyer_name": "PT Klien Sejahtera",
    "buyer_address": "-",
    "buyer_npwp": "02.345.678.9-012.000",
    "line_items": [
      {
        "description": "Kamar Deluxe x 2 malam",
        "quantity": 2.0,
        "unit_price": 850000.0,
        "subtotal": 1700000.0
      }
    ],
    "subtotal": 1700000.0,
    "discount": 0.0,
    "tax": 187000.0,
    "total_payment": 1887000.0,
    "currency": "IDR",
    "payment_terms": "NET 14",
    "authenticity": {
      "verdict": "AUTENTIK",
      "is_suspicious": false,
      "confidence_score": 0.95,
      "detected_provider": "traveloka",
      "pdf_creator": "Skia/PDF",
      "pdf_producer": "Chrome",
      "creation_date": "2026-05-10T10:30:00",
      "modification_date": "2026-05-10T10:30:00",
      "was_modified": false,
      "warning_flags": [],
      "fake_evidence": [],
      "analysis_notes": "Tidak ada indikasi kecurangan."
    },
    "extraction_confidence": 0.85,
    "requires_manual_review": false,
    "review_reasons": [],
    "summary": "Invoice PT Hotel Indah, INV-2026/001, Total: Rp 1.887.000."
  }
}
```

### Response 200 — `data` untuk Receipt

```json
{
  "trx_id": "550e8400-...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "receipt",
    "receipt_number": "TRX-987654321",
    "transaction_date": "2026-05-12",
    "payment_date": "2026-05-12",
    "merchant_name": "Garuda Indonesia",
    "merchant_address": "Bandara Soekarno-Hatta",
    "merchant_phone": "0804-1-807-807",
    "payer_name": "Budi Santoso",
    "payer_email": "budi@klien.co.id",
    "payer_phone": "08123456789",
    "items_purchased": [
      {
        "description": "Tiket CGK→DPS 2026-05-15",
        "quantity": 1.0,
        "price": 1250000.0
      }
    ],
    "subtotal": 1250000.0,
    "tax": 0.0,
    "service_fee": 25000.0,
    "total_payment": 1275000.0,
    "currency": "IDR",
    "payment_method": "Kartu Kredit",
    "payment_status": "paid",
    "authenticity": { /* sama struktur seperti di atas */ },
    "extraction_confidence": 0.85,
    "requires_manual_review": false,
    "review_reasons": [],
    "summary": "Garuda Indonesia CGK→DPS 2026-05-15. Total: Rp 1.275.000."
  }
}
```

### Response 200 — `data` untuk Unknown

```json
{
  "trx_id": "550e8400-...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "unknown",
    "authenticity": {
      "verdict": "MENCURIGAKAN",
      "is_suspicious": true,
      "confidence_score": 0.5,
      "detected_provider": "-",
      "pdf_creator": "Microsoft Word",
      "pdf_producer": "Word PDF Exporter",
      "creation_date": "2026-05-15T08:00:00",
      "modification_date": "2026-05-15T08:00:00",
      "was_modified": false,
      "warning_flags": ["editing_software_detected", "unknown_provider"],
      "fake_evidence": ["[BUKTI - SOFTWARE PENGEDITAN] Dokumen dibuat menggunakan Microsoft Word..."],
      "analysis_notes": "Ditemukan 2 indikator."
    },
    "extraction_confidence": 0.0,
    "requires_manual_review": true,
    "review_reasons": ["Dokumen tidak dikenali sebagai invoice atau receipt."],
    "summary": "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
  }
}
```

**Catatan**: Untuk `unknown`, field invoice/receipt tidak ada — hanya field common (`doc_type`, `authenticity`, `extraction_confidence`, `requires_manual_review`, `review_reasons`, `summary`).

### Response masih progress

Sama seperti sebelumnya. Belum ada `data`:

```json
{
  "trx_id": "550e8400-...",
  "status": "progress",
  "message": "Dokumen sedang diproses.",
  "data": null
}
```

### Error responses

Sama seperti sebelumnya: `TRX_NOT_FOUND` (404), `TRX_EXPIRED` (410), `INTERNAL_ERROR` (500), `UNAUTHORIZED` (401).

## 3. Discriminator Rules untuk Konsumen

Cara PISmart parse response `success`:

```python
if data["doc_type"] == "invoice":
    invoice = InvoiceModel(**data)
elif data["doc_type"] == "receipt":
    receipt = ReceiptModel(**data)
elif data["doc_type"] == "unknown":
    # Tampilkan ke operator untuk klasifikasi manual
    show_manual_review(data["authenticity"], data["review_reasons"])
```

## 4. Migration Notes untuk PISmart

| Field lama | Field baru | Catatan |
|------------|-----------|---------|
| (tidak ada `doc_type`) | `data.doc_type` | Selalu hadir di response success |
| Schema hotel (`order_id`, `hotel_name`...) | Schema invoice (`invoice_number`, `vendor_name`...) | Bukan migrasi 1:1, namanya formal-akuntansi |
| Schema flight (`receipt_number`, `airline`, `route_*`) | Schema receipt (`receipt_number`, `merchant_name`, `items_purchased`) | Items dipindah ke array `items_purchased` |

PISmart **harus** baca `doc_type` dulu sebelum parse `data`. Tidak boleh asumsikan schema.

## 5. Versioning

Endpoint **tidak** diversion-kan (`v2`). Alasan:
- Bukan breaking change pada envelope (`trx_id`/`status`/`message`/`data` tetap)
- Field `data.doc_type` adalah additive
- PISmart sebagai satu-satunya konsumen akan di-update bersamaan
