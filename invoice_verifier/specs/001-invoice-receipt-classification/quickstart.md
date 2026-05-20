# Quickstart: Invoice & Receipt Classification

**Tujuan**: Panduan singkat developer untuk mengerjakan implementasi fitur ini.

## Yang Berubah dalam 1 Menit

| Sebelum | Sesudah |
|---------|---------|
| `classify_document` → `flight` / `hotel` / `unknown` | `invoice` / `receipt` / `unknown` |
| `flight_agent`, `hotel_agent` | `invoice_agent`, `receipt_agent` |
| `FlightTicketResult`, `HotelInvoiceResult` | `InvoiceResult`, `ReceiptResult`, `UnknownResult` |
| Unknown → fallback ke `hotel` agent | Unknown → **tanpa AI**, langsung default + authenticity |
| Tidak ada `doc_type` di response | `data.doc_type` selalu ada |

## Urutan Pekerjaan

Tahap sebaiknya dikerjakan urut karena ada ketergantungan:

### Tahap 1 — Models (paling independent)

1. Buat 3 file model baru:
   - `baca_invoice/models/invoice.py` → `InvoiceResult`, `InvoiceLineItem`
   - `baca_invoice/models/receipt.py` → `ReceiptResult`, `ReceiptItem`
   - `baca_invoice/models/unknown.py` → `UnknownResult`
2. Update `baca_invoice/models/__init__.py` untuk export semua model baru
3. Tulis unit test untuk validasi default values dan Literal `doc_type`

### Tahap 2 — Classifier (independent dari Tahap 1)

1. Edit `web/services/agent_runner.py`:
   - Ganti `_FLIGHT_KEYWORDS` → `_RECEIPT_KEYWORDS = {"receipt", "struk", "bukti bayar", "kwitansi", "e-tiket", "e-ticket", "booking confirmation", "payment confirmation", "lunas", "paid"}`
   - Ganti `_HOTEL_KEYWORDS` → `_INVOICE_KEYWORDS = {"invoice", "faktur", "tagihan", "ppn", "vat", "npwp", "nomor faktur", "jatuh tempo", "due date"}`
   - Ubah return type: `Literal["invoice", "receipt", "unknown"]`
   - Hapus logika fallback ke "hotel" — biarkan `"unknown"` keluar
2. Update logika `_detect_by_provider` agar mapping ke invoice/receipt baru

### Tahap 3 — Agents (tergantung Tahap 1)

1. Buat `baca_invoice/agents/invoice.py`:
   ```python
   from google.adk.agents import LlmAgent
   from ..tools.combined import analyze_document
   from .prompts import INVOICE_PROMPT

   invoice_agent = LlmAgent(
       name="invoice_agent",
       model="gemini-2.5-flash",
       instruction=INVOICE_PROMPT,
       tools=[analyze_document],
   )
   ```
2. Buat `baca_invoice/agents/receipt.py` (struktur sama)
3. Tambah `INVOICE_PROMPT` dan `RECEIPT_PROMPT` di `prompts.py`:
   - Salin pola `FLIGHT_SINGLE` / `HOTEL_SINGLE`
   - Ganti `FORMAT JSON WAJIB` sesuai schema baru (lihat data-model.md)
   - Tambah `"doc_type": "invoice"` / `"doc_type": "receipt"` di JSON output

### Tahap 4 — Service Layer (tergantung Tahap 2 & 3)

1. Edit `AgentRunnerService.__init__`:
   - Ganti `self._flight_runner` → `self._receipt_runner`
   - Ganti `self._hotel_runner` → `self._invoice_runner`
2. Edit `AgentRunnerService.run_job`:
   - Routing baru: `runner = self._invoice_runner if doc_type == "invoice" else self._receipt_runner`
   - Update `_DOC_TYPE_LABEL` ke `{"invoice": "Invoice", "receipt": "Receipt", "unknown": "Dokumen"}`
3. **PENTING**: Untuk unknown, **jangan** panggil agent. Kembalikan langsung `UnknownResult` dengan `authenticity` dari tools.

### Tahap 5 — API Layer (tergantung Tahap 4)

Edit `web/api/v1_upload.py`:

```python
# Pseudocode di _run_and_persist
if job.doc_type == "unknown":
    # Skip AI — langsung build UnknownResult
    from baca_invoice.tools.authenticity import analyze_document_authenticity
    from baca_invoice.models.unknown import UnknownResult

    auth = analyze_document_authenticity(job.file_path)
    result = UnknownResult(authenticity=DocumentAuthenticity(**auth))
    await update_job(trx_id, status="success", result_json=result.model_dump())
else:
    # Existing path: run agent
    await runner_service.run_job(trx_id)
    ...
```

Hapus juga logika fallback `doc_type_unknown = doc_type == "unknown"; doc_type = "hotel"` — tidak relevan lagi.

### Tahap 6 — Cleanup

Hapus file lama:
- `baca_invoice/models/flight.py`
- `baca_invoice/models/hotel.py`
- `baca_invoice/agents/flight.py`
- `baca_invoice/agents/hotel.py`
- Constant `FLIGHT_SINGLE` & `HOTEL_SINGLE` di `prompts.py`

### Tahap 7 — Tests

1. Update `tests/integration/test_upload.py`:
   - Sesuaikan `stub_classify` untuk return "invoice", "receipt", atau "unknown"
   - Tambah test: PDF mengandung "invoice" → klasifikasi `invoice`
   - Tambah test: PDF mengandung "e-tiket" → klasifikasi `receipt`
   - Tambah test: PDF kosong → klasifikasi `unknown` + response 200 + `doc_type` di data
2. Tambah unit test untuk `UnknownResult` defaults
3. Pastikan semua test passing

## Smoke Test Manual

```bash
# 1. Upload PDF invoice
curl -X POST http://localhost:8080/api/pinter/upload \
  -F "file=@invoice-hotel.pdf"
# Response: {"trx_id": "...", "status": "progress", ...}

# 2. Poll
curl http://localhost:8080/api/pinter/extract?trx_id=<trx_id>
# Setelah selesai:
# {"status": "success", "data": {"doc_type": "invoice", "invoice_number": "...", ...}}

# 3. Upload dokumen acak (mis. CV PDF)
curl -X POST http://localhost:8080/api/pinter/upload \
  -F "file=@cv.pdf"

# 4. Poll
curl http://localhost:8080/api/pinter/extract?trx_id=<trx_id>
# {"status": "success", "data": {"doc_type": "unknown", "extraction_confidence": 0.0, "requires_manual_review": true, ...}}
```

Kunci sukses smoke test:
- Tidak ada dokumen yang menghasilkan HTTP error
- `data.doc_type` selalu ada di response success
- Dokumen unknown kembali dalam **< 5 detik** (no AI call)

## Risiko & Mitigasi

| Risiko | Mitigasi |
|--------|----------|
| Heuristic keyword terlalu sederhana, dokumen invoice/receipt salah klasifikasi | Bisa diiterasi: tambah keyword berdasarkan data nyata; fallback ke `unknown` jika ambigu |
| AI agent baru hasilkan output tidak sesuai schema baru | Pakai Pydantic `model_validate` di `_parse_json_result`, log warning kalau tidak sesuai |
| Konsumen API (PISmart) lupa baca `doc_type` | Dokumentasikan di README + contracts/pinter-api.md; koordinasi sebelum deploy |

## Next Steps

1. Run `/speckit-tasks` untuk breakdown task ke level granular yang bisa dieksekusi
2. Run `/speckit-implement` untuk eksekusi otomatis
