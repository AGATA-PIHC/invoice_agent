# Invoice Verifier — API Reference

Base URL: `http://localhost:8080`

Autentikasi: header `X-API-Key` (env `PINTER_API_KEY`; nonaktif kalau tidak diset).
Format response error seragam:
```json
{ "status": "fail", "message": "...", "error_code": "MACHINE_READABLE_CODE" }
```

---

## Endpoints

### 1. `POST /api/pinter/upload`

Upload PDF untuk diekstraksi. Proses berjalan async di background.

**Request**:
- `Content-Type: multipart/form-data`
- Field `file`: PDF, max 20 MB (env `MAX_UPLOAD_MB`)
- Header `X-API-Key` (opsional, tergantung config)

**Response 200 — Doc type invoice/receipt**:
```json
{
  "trx_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "progress",
  "message": "Dokumen diterima dan sedang diproses."
}
```

**Response 200 — Doc type unknown**:
```json
{
  "trx_id": "...",
  "status": "progress",
  "message": "Dokumen diterima. Tidak dikenali sebagai invoice/receipt — akan dikembalikan dengan doc_type='unknown'."
}
```

**Response Errors**:

| HTTP | error_code | Penyebab |
|------|------------|----------|
| 400 | `MISSING_FILE` | Field `file` kosong |
| 400 | `INVALID_FILE_TYPE` | Bukan PDF (ekstensi/magic bytes) |
| 401 | `UNAUTHORIZED` | X-API-Key salah/tidak ada |
| 413 | `FILE_TOO_LARGE` | Melebihi 20 MB |
| 429 | `RATE_LIMITED` | > 10 upload/menit/IP |
| 500 | `INTERNAL_ERROR` | Error server |

---

### 2. `GET /api/pinter/extract?trx_id={trx_id}`

Poll hasil ekstraksi.

**Response 200 — Masih progress**:
```json
{
  "trx_id": "...",
  "status": "progress",
  "message": "Dokumen sedang diproses.",
  "data": null
}
```

**Response 200 — Success (doc_type=invoice)**:
```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "invoice",
    "invoice_number": "INV-2026/001",
    "vendor_name": "PT Hotel Indah",
    "buyer_name": "...",
    "line_items": [
      { "description": "...", "quantity": 2, "unit_price": 850000, "subtotal": 1700000 }
    ],
    "subtotal": 1700000.0,
    "tax": 187000.0,
    "total_payment": 1887000.0,
    "currency": "IDR",
    "authenticity": { /* DocumentAuthenticity */ },
    "extraction_confidence": 0.85,
    "requires_manual_review": false,
    "summary": "Invoice PT Hotel Indah, INV-2026/001, Total: Rp 1.887.000."
  }
}
```

**Response 200 — Success (doc_type=receipt)**:
```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "receipt",
    "receipt_number": "TRX-987654321",
    "merchant_name": "Garuda Indonesia",
    "payer_name": "Budi Santoso",
    "items_purchased": [
      { "description": "Tiket CGK→DPS", "quantity": 1, "price": 1250000 }
    ],
    "total_payment": 1275000.0,
    "currency": "IDR",
    "payment_method": "Kartu Kredit",
    "payment_status": "paid",
    "authenticity": { /* DocumentAuthenticity */ },
    "extraction_confidence": 0.85,
    "summary": "Garuda Indonesia CGK→DPS. Total: Rp 1.275.000."
  }
}
```

**Response 200 — Success (doc_type=unknown)**:

Untuk dokumen tidak terklasifikasi, sistem **tidak memanggil AI** — hanya analisis `authenticity` PDF.

```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "unknown",
    "authenticity": { /* DocumentAuthenticity */ },
    "extraction_confidence": 0.0,
    "requires_manual_review": true,
    "review_reasons": ["Dokumen tidak dikenali sebagai invoice atau receipt."],
    "summary": "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
  }
}
```

**Response 200 — Status fail**:
```json
{
  "trx_id": "...",
  "status": "fail",
  "message": "Verifikasi gagal: <detail>",
  "data": null
}
```

**Response Errors**:

| HTTP | error_code | Penyebab |
|------|------------|----------|
| 400 | `MISSING_TRX_ID` | Query `trx_id` tidak ada |
| 400 | `VALIDATION_ERROR` | Format param tidak valid |
| 401 | `UNAUTHORIZED` | X-API-Key salah/tidak ada |
| 404 | `TRX_NOT_FOUND` | trx_id tidak ada di DB |
| 410 | `TRX_EXPIRED` | trx_id > `PINTER_TRX_TTL_DAYS` (default 7 hari) |
| 500 | `INTERNAL_ERROR` | Error server |

---

### 3. `GET /health`

Liveness check.

**Response 200**:
```json
{
  "status": "ok",
  "jobs_active": 0
}
```

---

## DocumentAuthenticity Schema

Sub-schema yang muncul di response semua doc_type:

```json
{
  "verdict": "AUTENTIK",
  "is_suspicious": false,
  "confidence_score": 0.95,
  "detected_provider": "tiket.com",
  "pdf_creator": "Mozilla/5.0...HeadlessChrome...",
  "pdf_producer": "Skia/PDF m140",
  "creation_date": "2026-04-23T14:17:38",
  "modification_date": "2026-04-23T14:17:38",
  "was_modified": false,
  "warning_flags": [],
  "fake_evidence": [],
  "analysis_notes": "Tidak ditemukan indikator kecurangan."
}
```

`verdict` values: `AUTENTIK` | `MENCURIGAKAN` | `PALSU/DIEDIT` | `-`

---

## Klasifikasi 2 Dimensi

Sistem mengklasifikasikan dokumen pada 2 dimensi independen, keduanya dikerjakan
oleh `document_agent` dalam satu LLM call:

1. **`doc_type`** → `"invoice"` / `"receipt"` / `"unknown"` (kategori publik)
2. **`document_subtype`** → `"hotel"` / `"flight"` / `"unknown"`

Field `data.doc_type` di response **selalu** `invoice` / `receipt` / `unknown` —
tidak pernah `hotel` / `flight`. Subtype dilaporkan di `data.document_subtype`.

---

## Klien Contoh

### curl

```bash
# Upload
curl -X POST http://localhost:8080/api/pinter/upload \
  -H "X-API-Key: your_key" \
  -F "file=@invoice.pdf"

# Poll
curl "http://localhost:8080/api/pinter/extract?trx_id=550e8400-..." \
  -H "X-API-Key: your_key"
```

### Python (httpx)

```python
import httpx, time

API = "http://localhost:8080"
HEADERS = {"X-API-Key": "your_key"}

with httpx.Client() as c:
    with open("invoice.pdf", "rb") as f:
        r = c.post(f"{API}/api/pinter/upload", files={"file": f}, headers=HEADERS)
    r.raise_for_status()
    trx_id = r.json()["trx_id"]

    while True:
        r = c.get(f"{API}/api/pinter/extract", params={"trx_id": trx_id}, headers=HEADERS)
        data = r.json()
        if data["status"] != "progress":
            break
        time.sleep(1.5)

    if data["status"] == "success":
        result = data["data"]
        print(f"doc_type: {result['doc_type']}")
        print(f"summary: {result['summary']}")
```

### JavaScript (browser)

```javascript
// Optional: set API key once via DevTools console
localStorage.setItem('pinterApiKey', '<key>');

const headers = () => {
  const k = localStorage.getItem('pinterApiKey');
  return k ? { 'X-API-Key': k } : {};
};

// Upload
const form = new FormData();
form.append('file', fileObj);
const up = await fetch('/api/pinter/upload', { method: 'POST', body: form, headers: headers() });
const { trx_id } = await up.json();

// Poll
while (true) {
  const r = await fetch(`/api/pinter/extract?trx_id=${trx_id}`, { headers: headers() });
  const body = await r.json();
  if (body.status !== 'progress') break;
  await new Promise(r => setTimeout(r, 1500));
}
```
