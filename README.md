# Invoice Agent

Agent berbasis [Google ADK](https://google.github.io/adk-docs/) untuk verifikasi keaslian dokumen perjalanan dinas — tiket pesawat dan invoice hotel dalam format PDF.

## Fitur

- Ekstraksi data terstruktur dari PDF tiket pesawat (Traveloka, AirAsia, Garuda, Lion Air, dll.)
- Ekstraksi data terstruktur dari PDF invoice hotel (Tiket.com, Booking.com, dll.)
- Deteksi keaslian dokumen: metadata PDF, software pengedit, modifikasi pasca-pembuatan
- Output JSON terstruktur dengan confidence score dan verdict (AUTENTIK / MENCURIGAKAN / PALSU)

## Struktur Project

```
adk_workspace/
├── baca_invoice/
│   ├── agent.py          # Root agent (koordinator)
│   ├── agents/
│   │   ├── flight.py     # Sub-agent tiket pesawat
│   │   ├── hotel.py      # Sub-agent invoice hotel
│   │   └── prompts.py    # Prompt semua agent
│   ├── models/
│   │   ├── flight.py     # Pydantic model output tiket pesawat
│   │   ├── hotel.py      # Pydantic model output invoice hotel
│   │   └── authenticity.py
│   └── tools/
│       ├── pdf.py        # Tool ekstraksi konten PDF
│       ├── authenticity.py # Tool analisis keaslian PDF
│       └── constants.py  # Daftar provider & software edit
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

# macOS/Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Konfigurasi environment**

```bash
cp baca_invoice/.env_example .env
```

Edit `.env` dan isi dengan API key:

```env
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=your_google_api_key_here
```

## Cara Menjalankan

Jalankan ADK web UI dari root project:

```bash
adk web
```

Buka browser di `http://localhost:8000`, pilih agent **`baca_invoice`**, lalu kirim perintah seperti:

```
Verifikasi file ini: C:/path/to/invoice.pdf
```

Agent akan otomatis mendeteksi jenis dokumen (pesawat atau hotel) dan mengembalikan hasil verifikasi dalam format JSON.

### Contoh Output

```json
{
  "summary": "Garuda Indonesia CGK-DPS tgl 2024-03-15. Total: Rp 1.250.000. Verdict: AUTENTIK.",
  "authenticity": {
    "verdict": "AUTENTIK",
    "is_suspicious": false,
    "confidence_score": 0.95,
    "fake_evidence": []
  },
  "total_payment": 1250000.0,
  "requires_manual_review": false
}
```

## Menjalankan via CLI

```bash
adk run baca_invoice
```

Kemudian ketik instruksi di terminal, misalnya:

```
path: C:/dokumen/invoice_hotel.pdf
```
