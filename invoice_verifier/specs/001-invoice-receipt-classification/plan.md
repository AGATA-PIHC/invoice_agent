# Implementation Plan: Invoice & Receipt Classification

**Branch**: `002-upload-extract-api` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-invoice-receipt-classification/spec.md`

## Summary

Mengganti klasifikasi dokumen dari `flight`/`hotel` menjadi `invoice`/`receipt`/`unknown`. Untuk `unknown`, sistem mengembalikan Pydantic model bernilai default tanpa memanggil AI (analisis `authenticity` PDF tetap dijalankan).

## Technical Context

| Item | Nilai |
|------|-------|
| **Bahasa** | Python 3.11+ |
| **Framework backend** | FastAPI |
| **AI Framework** | Google ADK + Gemini 2.5 Flash |
| **PDF processing** | PyMuPDF (fitz) — sudah ada |
| **Validasi schema** | Pydantic v2 — sudah ada |
| **Storage** | SQLite (aiosqlite) — tidak berubah |
| **API endpoints** | PINTER `/api/pinter/upload` & `/api/pinter/extract` — tidak berubah |
| **Test framework** | pytest + httpx — sudah ada |

**Tidak ada NEEDS CLARIFICATION** — semua pertanyaan sudah dijawab di Phase 0 spec.

## Constitution Check

Tidak ada `.specify/memory/constitution.md` di project. Mengacu pada prinsip implisit yang sudah terbentuk dari commit history:
- API contract tidak boleh breaking — ✓ FR-5 mengamanatkan ini
- Pendekatan testable — ✓ semua FR memiliki acceptance criteria
- Tidak menambah dependency baru jika bisa pakai yang ada — ✓ Pydantic, fitz, FastAPI sudah cukup
- Async-first di service layer — ✓ tidak ada blocking call baru

**Status**: PASS

## Project Structure

### Documentation (this feature)

```
specs/001-invoice-receipt-classification/
├── spec.md                 # Feature specification (Phase -1)
├── plan.md                 # This file
├── research.md             # Phase 0 output
├── data-model.md           # Phase 1: Pydantic schemas
├── contracts/
│   └── pinter-api.md       # Phase 1: API contract
├── quickstart.md           # Phase 1: dev quick start
└── checklists/
    └── requirements.md
```

### Source Code (yang akan disentuh)

```
invoice_verifier/
├── baca_invoice/
│   ├── agents/
│   │   ├── invoice.py          # NEW: agent untuk invoice
│   │   ├── receipt.py          # NEW: agent untuk receipt
│   │   └── prompts.py          # MODIFY: tambah INVOICE_PROMPT, RECEIPT_PROMPT
│   ├── models/
│   │   ├── invoice.py          # NEW: InvoiceResult Pydantic model
│   │   ├── receipt.py          # NEW: ReceiptResult Pydantic model
│   │   └── unknown.py          # NEW: UnknownResult Pydantic model
│   └── tools/
│       └── (tidak berubah)
└── web/
    ├── api/
    │   └── v1_upload.py        # MODIFY: handle doc_type unknown tanpa AI
    └── services/
        └── agent_runner.py     # MODIFY: classify_document → invoice/receipt/unknown
                                #         + handle unknown tanpa AI
```

**File lama** (`flight.py`, `hotel.py` di models & agents) akan **dihapus** setelah migrasi selesai.

## Phase 0: Research

Lihat [research.md](./research.md) — keputusan teknis sudah dikonsolidasi.

## Phase 1: Design

- [data-model.md](./data-model.md) — Pydantic schema untuk Invoice, Receipt, UnknownResult
- [contracts/pinter-api.md](./contracts/pinter-api.md) — kontrak API yang tetap kompatibel
- [quickstart.md](./quickstart.md) — panduan singkat developer

## Phase 2: Implementation Roadmap

Akan dijabarkan lebih detail di `/speckit-tasks`. Garis besar:

1. **Schema layer** (independent):
   - Buat `models/invoice.py`, `models/receipt.py`, `models/unknown.py`
   - Update `models/__init__.py` untuk export

2. **Classification layer** (independent):
   - Refactor `classify_document()` di `agent_runner.py` — ganti keyword set dari flight/hotel ke invoice/receipt
   - Return `Literal["invoice", "receipt", "unknown"]`
   - Tambah keyword set untuk: faktur, ppn, tagihan (invoice) vs e-tiket, struk, bukti bayar (receipt)

3. **Agent layer** (depends on schema):
   - Buat `agents/invoice.py` dan `agents/receipt.py` dengan prompt yang sesuai
   - Tambah `INVOICE_PROMPT` dan `RECEIPT_PROMPT` di `prompts.py`
   - Hapus `flight.py`, `hotel.py` agents
   - Update `AgentRunnerService.__init__` untuk inisialisasi 2 runner baru

4. **API layer** (depends on agent):
   - Update `v1_upload.py`: jika `doc_type == "unknown"`, **skip** AI call, langsung tulis `UnknownResult` ke DB sebagai hasil `success`
   - Pastikan `authenticity` tetap dijalankan untuk unknown (panggil `analyze_document_authenticity` langsung dari `tools/authenticity.py`)
   - Tambah `doc_type` di response data

5. **Cleanup**:
   - Hapus `baca_invoice/models/flight.py`, `hotel.py`
   - Hapus `baca_invoice/agents/flight.py`, `hotel.py`
   - Hapus `FLIGHT_SINGLE`, `HOTEL_SINGLE` di `prompts.py`

6. **Tests**:
   - Update test untuk klasifikasi (assert "invoice"/"receipt"/"unknown")
   - Tambah test untuk skenario unknown tanpa AI
   - Tambah test untuk verifikasi `doc_type` di response

## Progress

| Phase | Status |
|-------|--------|
| Spec | ✅ Selesai |
| Plan (this file) | ✅ Selesai |
| Research | ✅ Selesai |
| Data model | ✅ Selesai |
| Contracts | ✅ Selesai |
| Quickstart | ✅ Selesai |
| Tasks (`/speckit-tasks`) | ⏳ Berikutnya |
| Implementation (`/speckit-implement`) | ⏳ Menanti |
