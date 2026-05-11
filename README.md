# Invoice Verifier

Aplikasi web untuk verifikasi keaslian dokumen perjalanan dinas — tiket pesawat dan invoice hotel dalam format PDF. Dibangun dengan [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) dan FastAPI.

## Fitur

- Upload PDF via drag & drop atau file picker langsung dari browser
- Deteksi otomatis jenis dokumen (tiket pesawat / invoice hotel) tanpa LLM
- Ekstraksi data terstruktur: rute, tanggal, harga, vendor, penumpang/tamu
- Analisis keaslian: metadata PDF, software pengedit, tanda modifikasi pasca-cetak
- Verdict per dokumen: **AUTENTIK**, **MENCURIGAKAN**, atau **PALSU** dengan confidence score
- Streaming real-time aktivitas agent via Server-Sent Events (SSE)
- Rate limiting dan HMAC token untuk keamanan upload

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
│       ├── api/verify.py       # Endpoint upload & SSE stream
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

Edit `.env` dan isi `GOOGLE_API_KEY`:

```env
GOOGLE_API_KEY=your-google-api-key-here
APP_ENV=development
```

## Menjalankan Web App

```bash
python run_web.py
```

Buka browser di `http://localhost:8080`, upload file PDF, dan tunggu hasil verifikasi.

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

## Contoh Output

```json
{
  "verdict": "AUTENTIK",
  "is_suspicious": false,
  "confidence_score": 0.95,
  "detected_provider": "Garuda Indonesia",
  "warning_flags": [],
  "summary": "Garuda Indonesia CGK-DPS, 15 Mar 2024. Total: Rp 1.250.000.",
  "passenger_name": "Budi Santoso",
  "departure": "Jakarta (CGK)",
  "destination": "Denpasar (DPS)",
  "departure_date": "2024-03-15",
  "total_payment": 1250000.0,
  "requires_manual_review": false
}
```

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Agent framework | Google ADK + Gemini 2.5 Flash |
| Web server | FastAPI + Uvicorn |
| PDF processing | PyMuPDF (fitz) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | Vanilla JS, CSS glassmorphism |
| Testing | pytest + pytest-asyncio + httpx |
