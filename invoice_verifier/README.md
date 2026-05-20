# Invoice Verifier - PINTER

FastAPI service untuk upload PDF dokumen perjalanan dinas, memprosesnya dengan satu
Google ADK agent, lalu menyimpan hasil ekstraksi ke SQLite untuk diambil dengan `trx_id`.

## Endpoint

| Method | Path | Fungsi |
| --- | --- | --- |
| `POST` | `/api/pinter/upload` | Upload PDF, return `trx_id`, proses async |
| `GET` | `/api/pinter/extract?trx_id={trx_id}` | Poll hasil ekstraksi |
| `GET` | `/health` | Health check |

Autentikasi memakai header `X-API-Key` jika env `PINTER_API_KEY` diset.

## Flow Utama

```text
POST /api/pinter/upload
  -> validasi PDF dan ukuran file
  -> simpan file ke tmp_uploads/{trx_id}/
  -> insert job progress ke SQLite
  -> jalankan background task AgentRunnerService.run_job()
  -> response langsung: { trx_id, status: "progress" }

AgentRunnerService.run_job()
  -> document_agent membaca PDF via analyze_document(file_path)
  -> document_agent menentukan doc_type: invoice / receipt / unknown
  -> document_agent menentukan document_subtype: hotel / flight / unknown
  -> jika subtype hotel/flight, document_agent dapat memakai AgentTool helper
  -> hasil dinormalisasi oleh formatter_agent ke TravelDocumentResult
  -> hasil valid disimpan ke SQLite sebagai status success

GET /api/pinter/extract?trx_id=...
  -> baca row SQLite
  -> return progress / fail / success + data JSON
```

## Agent Runtime

Runtime API hanya memakai satu agent utama:

- `baca_invoice/agents/document.py` - `document_agent`
- `baca_invoice/agents/formatter.py` - normalisasi schema output
- `baca_invoice/agents/hotel.py` - AgentTool helper detail hotel
- `baca_invoice/agents/flight.py` - AgentTool helper detail flight

`document_agent` adalah source of truth untuk:

- `doc_type`: `invoice`, `receipt`, atau `unknown`
- `document_subtype`: `hotel`, `flight`, atau `unknown`

Backend tidak melakukan routing ke agent spesifik. `hotel_agent` dan `flight_agent`
hanya dipakai sebagai tools internal oleh `document_agent`.

## Struktur Kode Penting

```text
web/
  main.py                    FastAPI app, lifespan, error handlers
  api/v1_upload.py           Endpoint upload/extract
  db/sqlite.py               CRUD SQLite upload_jobs
  services/agent_runner.py   Runner ADK, validasi hasil, cleanup file

baca_invoice/
  agent.py                   ADK root_agent = document_agent
  agents/document.py         Agent klasifikasi + ekstraksi
  agents/hotel.py            Helper AgentTool untuk detail hotel
  agents/flight.py           Helper AgentTool untuk detail flight
  agents/formatter.py        Agent normalisasi schema
  agents/prompts.py          Prompt document/hotel/flight helper
  models/travel_document.py  Schema JSON final
  tools/combined.py          Tool analyze_document
  tools/pdf.py               Ekstraksi teks/metadata PDF
  tools/authenticity.py      Analisis authenticity
```

## Output JSON

Semua response success memakai envelope:

```json
{
  "trx_id": "...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "doc_type": "invoice",
    "document_subtype": "hotel"
  }
}
```

Nilai valid:

- `doc_type`: `invoice`, `receipt`, `unknown`
- `document_subtype`: `hotel`, `flight`, `unknown`

Untuk `unknown`, backend memastikan:

- `document_subtype = "unknown"`
- `extraction_confidence = 0.0`
- `requires_manual_review = true`

## Konfigurasi

Salin `baca_invoice/.env_example` ke `baca_invoice/.env` dan isi env yang dibutuhkan.

| Env | Fungsi | Default |
| --- | --- | --- |
| `GOOGLE_API_KEY` | API key Google AI Studio | wajib |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` untuk Vertex AI, `0` untuk AI Studio | `0` |
| `PINTER_API_KEY` | API key endpoint PINTER | kosong |
| `PINTER_TRX_TTL_DAYS` | TTL `trx_id` | `7` |
| `SQLITE_DB_PATH` | Lokasi SQLite DB | `data/invoice_verifier.db` |
| `MAX_UPLOAD_MB` | Batas upload PDF | `20` |
| `MAX_CONCURRENT_JOBS` | Batas job AI paralel | `10` |

## Menjalankan

```powershell
uvicorn web.main:app --host 0.0.0.0 --port 8080
```

## Contoh API

Upload:

```powershell
curl -X POST http://localhost:8080/api/pinter/upload `
  -H "X-API-Key: your_key" `
  -F "file=@invoice.pdf"
```

Poll:

```powershell
curl "http://localhost:8080/api/pinter/extract?trx_id={trx_id}" `
  -H "X-API-Key: your_key"
```

## Error Code

| Code | HTTP | Penyebab |
| --- | --- | --- |
| `MISSING_FILE` | 400 | Field `file` kosong |
| `MISSING_TRX_ID` | 400 | Query `trx_id` kosong |
| `INVALID_FILE_TYPE` | 400 | File bukan PDF |
| `FILE_TOO_LARGE` | 413 | Ukuran file melewati batas |
| `RATE_LIMITED` | 429 | Terlalu banyak upload per menit |
| `TRX_NOT_FOUND` | 404 | `trx_id` tidak ditemukan |
| `TRX_EXPIRED` | 410 | `trx_id` kedaluwarsa |
| `UNAUTHORIZED` | 401 | API key salah/tidak ada |
| `INTERNAL_ERROR` | 500 | Error internal |
