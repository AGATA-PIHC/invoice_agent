# Invoice Verifier

Aplikasi verifikasi keaslian dokumen perjalanan dinas — tiket pesawat dan invoice hotel dalam format PDF. Dibangun dengan [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) dan FastAPI.

## Fitur

- Upload PDF via multipart/form-data (integrasi M2M dengan PISmart)
- Deteksi otomatis jenis dokumen (tiket pesawat / invoice hotel) tanpa LLM
- Ekstraksi data terstruktur: rute, tanggal, harga, vendor, penumpang/tamu
- Analisis keaslian: metadata PDF, software pengedit, tanda modifikasi pasca-cetak
- Verdict per dokumen: **AUTENTIK**, **MENCURIGAKAN**, atau **PALSU** dengan confidence score
- Proses asynchronous dengan status tracking via polling

## Struktur Project

```
adk_workspace/
├── invoice_verifier/
│   ├── baca_invoice/           # Core agent package (Google ADK)
│   │   ├── agent.py            # Entry point ADK CLI
│   │   ├── agents/
│   │   │   ├── flight.py       # LlmAgent tiket pesawat
│   │   │   ├── hotel.py        # LlmAgent invoice hotel
│   │   │   └── prompts.py      # System prompt semua agent
│   │   ├── models/             # Pydantic output models
│   │   └── tools/
│   │       ├── combined.py     # Tool utama: baca PDF + analisis sekaligus
│   │       ├── pdf.py          # Ekstraksi konten & metadata PDF
│   │       ├── authenticity.py # Analisis keaslian dokumen
│   │       └── constants.py    # Daftar provider & software pengedit
│   └── web/                    # FastAPI web server
│       ├── main.py             # App entrypoint & lifespan
│       ├── config.py           # Konfigurasi dari env vars
│       ├── api/v1_upload.py    # PINTER API endpoints
│       ├── db/sqlite.py        # Persistent storage (SQLite)
│       ├── services/
│       │   └── agent_runner.py # Manajemen job & routing ke agent
│       └── static/             # Frontend (HTML + CSS + JS)
├── tests/                      # Unit, integration & security tests
├── run_web.py                  # Jalankan web server
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Prasyarat

- Python 3.11+
- Google AI Studio API Key → [aistudio.google.com](https://aistudio.google.com/app/apikey)

## Instalasi

**1. Clone repository**

```bash
git clone https://github.com/purba-naka/invoice_agent.git
cd invoice_agent
```

**2. Buat virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Konfigurasi environment**

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_API_KEY=your-google-api-key-here
APP_ENV=development
PINTER_API_KEY=your-api-key-here
```

## Menjalankan Web App

```bash
python run_web.py
```

Atau dengan auto-reload saat development:

```bash
python run_web.py --reload
```

## Menjalankan via Docker

```bash
docker build -t invoice-verifier .
docker run -p 8080:8080 --env-file .env invoice-verifier
```

## Menjalankan via ADK CLI

```bash
adk run baca_invoice
```

Kemudian kirim path file di terminal:

```
file_path: /path/to/dokumen.pdf
```

## Menjalankan Tests

```bash
pytest tests/ -v
```

## API Endpoint

Base URL: `http://localhost:8080`

Autentikasi: `X-API-Key` header (dinonaktifkan otomatis jika `PINTER_API_KEY` tidak di-set).

### POST `/api/pinter/upload`

Upload file PDF invoice untuk diekstraksi. Proses berjalan di background.

**Request** — `multipart/form-data`

| Field | Tipe | Keterangan |
|---|---|---|
| `file` | file | File PDF, maks 20 MB |

**Response `200`**

```json
{
  "trx_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "progress",
  "message": "Dokumen diterima dan sedang diproses."
}
```

---

### GET `/api/pinter/extract?trx_id={trx_id}`

Poll hasil ekstraksi. Ulangi setiap 3–5 detik sampai `status` bukan `progress`.

**Query Param**

| Param | Tipe | Keterangan |
|---|---|---|
| `trx_id` | string (UUID) | ID dari response upload |

**Response `200` — masih diproses**

```json
{
  "trx_id": "550e8400-...",
  "status": "progress",
  "message": "Dokumen sedang diproses.",
  "data": null
}
```

**Response `200` — selesai**

```json
{
  "trx_id": "550e8400-...",
  "status": "success",
  "message": "Ekstraksi berhasil.",
  "data": {
    "verdict": "AUTENTIK",
    "confidence_score": 0.95,
    "detected_provider": "traveloka",
    "traveler_name": "Budi Santoso",
    "airline": "Garuda Indonesia",
    "route_from": "CGK",
    "route_to": "DPS",
    "flight_date": "2024-03-15",
    "total_payment": 1250000.0,
    "currency": "IDR",
    "requires_manual_review": false,
    "summary": "Garuda Indonesia CGK→DPS 2024-03-15. Total: Rp 1.250.000. Verdict: AUTENTIK."
  }
}
```

**Response `200` — gagal**

```json
{
  "trx_id": "550e8400-...",
  "status": "fail",
  "message": "Ekstraksi gagal.",
  "data": null
}
```

**Status Enum**

| Status | Arti |
|---|---|
| `progress` | Masih diproses, poll lagi |
| `success` | Selesai, `data` tersedia |
| `fail` | Gagal diproses |

**Error Codes**

| `error_code` | HTTP | Kondisi |
|---|---|---|
| `MISSING_FILE` | 400 | Field `file` tidak ada |
| `INVALID_FILE_TYPE` | 400 | Bukan PDF atau magic bytes salah |
| `FILE_TOO_LARGE` | 413 | Melebihi 20 MB |
| `TRX_NOT_FOUND` | 404 | `trx_id` tidak dikenal |
| `TRX_EXPIRED` | 410 | `trx_id` sudah > 7 hari |
| `INTERNAL_ERROR` | 500 | Kesalahan internal server |
| `UNAUTHORIZED` | 401 | `X-API-Key` salah atau tidak ada |

---

### GET `/health`

Health check server.

**Response `200`**

```json
{
  "status": "ok",
  "jobs_active": 2
}
```

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Agent framework | Google ADK + Gemini 2.5 Flash |
| Web server | FastAPI + Uvicorn |
| PDF processing | PyMuPDF (fitz) |
| Persistent storage | SQLite (aiosqlite) |
| Frontend | Vanilla JS, CSS glassmorphism |
| Testing | pytest + pytest-asyncio + httpx |
