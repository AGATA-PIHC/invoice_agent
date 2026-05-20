# Research: Invoice & Receipt Classification

**Phase**: 0
**Tujuan**: Resolve semua pertanyaan teknis sebelum desain detail.

## Keputusan 1: Definisi Invoice vs Receipt

**Decision**: Mengikuti definisi akuntansi standar:
- **Invoice** = dokumen tagihan dari vendor sebelum atau saat pembayaran. Berisi `invoice_number`, info vendor lengkap (NPWP, alamat), line items, PPN, dan total yang harus dibayar.
- **Receipt** = bukti pembayaran setelah transaksi selesai. Berisi `receipt_number`, tanggal pembayaran, metode pembayaran, dan total yang sudah dibayar.

**Rationale**:
- Sesuai standar Indonesia untuk perjalanan dinas: invoice biasanya untuk klaim reimburse, receipt untuk bukti pengeluaran
- Distinksi konkret dan testable (kata kunci berbeda)

**Alternatif yang dipertimbangkan**:
- Klasifikasi berdasarkan sumber (hotel/flight/transport) — ditolak karena terlalu sempit; user ingin generalisasi
- Klasifikasi single doc_type dengan semua field — ditolak karena schema terlalu besar dan banyak field tidak relevan

## Keputusan 2: Strategi Klasifikasi (Heuristic vs AI)

**Decision**: Tetap pakai heuristic keyword + metadata, tanpa AI untuk klasifikasi.

Keyword baru:
- `_INVOICE_KEYWORDS` = {"invoice", "faktur", "tagihan", "ppn", "vat", "npwp", "nomor faktur", "jatuh tempo", "due date"}
- `_RECEIPT_KEYWORDS` = {"receipt", "struk", "bukti bayar", "kwitansi", "e-tiket", "e-ticket", "booking confirmation", "payment confirmation", "lunas", "paid"}

**Rationale**:
- Klasifikasi via AI menambah latensi 5–10 detik dan biaya API per dokumen
- Heuristic cukup akurat untuk dokumen perjalanan dinas Indonesia (terminologi standar)
- Tetap konsisten dengan pendekatan yang ada (current `classify_document` sudah heuristic)

**Alternatif**:
- Pakai AI agent kecil untuk klasifikasi — ditolak (lambat, mahal, overkill)
- ML classifier (BERT/sklearn) — ditolak (over-engineering untuk MVP)

## Keputusan 3: Handling Dokumen Unknown

**Decision**: **Tidak panggil AI**. Sistem mengembalikan `UnknownResult` Pydantic dengan field default, plus hasil `authenticity` dari analisis metadata PDF.

**Rationale**:
- Sesuai pilihan user (Opsi A di clarification)
- Hemat biaya API & latensi
- `authenticity` tetap berguna untuk menandai dokumen mencurigakan

**Implementasi**:
- Di `_run_and_persist`: deteksi `doc_type == "unknown"` sebelum memanggil `runner_service.run_job`
- Langsung jalankan `analyze_document_authenticity(file_path)` untuk dapat `authenticity`
- Bangun `UnknownResult(authenticity=..., extraction_confidence=0.0, requires_manual_review=True)`
- Tulis ke DB dengan status `success`

## Keputusan 4: Skema Response Konsisten

**Decision**: Tambah field `doc_type` di root setiap response `data` (di `ExtractResponse.data`).

```json
{
  "trx_id": "...",
  "status": "success",
  "data": {
    "doc_type": "invoice" | "receipt" | "unknown",
    ...field spesifik per type
    "authenticity": {...},
    "extraction_confidence": 0.0,
    "requires_manual_review": false,
    "summary": "..."
  }
}
```

**Rationale**:
- PISmart bisa baca `doc_type` dulu, lalu pilih schema yang sesuai
- Lebih clean daripada nested `{doc_type: ..., data: {...}}`
- Tidak breaking change — field baru saja

**Alternatif**:
- Tagged union (discriminated): `{"type": "invoice", "data": {...}}` — lebih formal tapi lebih nested
- Polymorphic schema dengan `Union[Invoice, Receipt, Unknown]` — tetap pakai, hanya tambah `doc_type` sebagai discriminator

## Keputusan 5: Migrasi dari Flight/Hotel ke Invoice/Receipt

**Decision**: Replace, bukan tambah. File `flight.py`, `hotel.py` dihapus.

**Rationale**:
- Tidak ada konsumen API yang bergantung pada label "flight"/"hotel" (sudah konsolidasi ke PINTER)
- Dual maintenance overhead tidak sepadan
- Field di Invoice/Receipt cukup superset dari Flight/Hotel (flight → receipt dengan items=[ticket]; hotel → invoice dengan line_items=[room])

**Mapping**:
- Tiket pesawat → `receipt` (e-tiket = bukti booking/payment)
- Invoice hotel → `invoice` (tagihan formal hotel)

## Keputusan 6: Authenticity untuk Unknown

**Decision**: Jalankan `analyze_document_authenticity` langsung dari `tools/authenticity.py` (bukan via agent), karena fungsi ini tidak memerlukan AI.

**Rationale**:
- `analyze_document_authenticity` adalah pure function yang menganalisis metadata PDF + text (no AI)
- Bisa dipanggil langsung di service layer untuk skenario unknown
- Konsisten dengan field requirement di spec (FR-3 acceptance: authenticity tetap terisi)

## Konsolidasi NEEDS CLARIFICATION

Tidak ada NEEDS CLARIFICATION tersisa dari spec.md. Pertanyaan di Assumptions sudah dijawab user (Opsi A).
