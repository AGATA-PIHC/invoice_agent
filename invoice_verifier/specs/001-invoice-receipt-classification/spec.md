# Feature: Invoice & Receipt Classification

## Overview

Saat ini sistem hanya mengenal dua jenis dokumen perjalanan: tiket pesawat dan invoice hotel. Fitur ini memperluas klasifikasi menjadi dua kategori yang lebih umum — **Invoice** dan **Receipt** — serta memastikan sistem tetap memproses dokumen yang tidak dikenali dengan mengembalikan respons JSON yang valid (bukan menolak).

**Invoice** adalah dokumen tagihan formal dari penyedia layanan, biasanya memuat detail pajak, nomor faktur, dan data perusahaan. **Receipt** adalah bukti pembayaran atau konfirmasi pemesanan, seperti e-tiket, booking confirmation, atau struk transaksi.

Dokumen yang tidak termasuk keduanya tetap diproses oleh sistem dan menghasilkan respons bertipe `unknown` dengan semua field bernilai default — tidak ada penolakan.

## Goals

- Membedakan Invoice dan Receipt secara eksplisit di seluruh sistem (klasifikasi, agent, response)
- Memastikan setiap dokumen apapun menghasilkan respons JSON yang valid dan terstruktur
- Menghilangkan perilaku penolakan implisit untuk dokumen yang tidak dikenali

## User Scenarios & Testing

### Skenario 1: Upload Invoice Formal
**Given**: PISmart mengirimkan file PDF berupa tagihan hotel atau invoice layanan bisnis
**When**: Sistem memproses dokumen
**Then**: Respons bertipe `invoice`, field terisi sesuai isi dokumen, `doc_type = "invoice"`

### Skenario 2: Upload Receipt / Bukti Bayar
**Given**: PISmart mengirimkan file PDF berupa e-tiket pesawat atau booking confirmation
**When**: Sistem memproses dokumen
**Then**: Respons bertipe `receipt`, field terisi sesuai isi dokumen, `doc_type = "receipt"`

### Skenario 3: Upload Dokumen Tidak Dikenal
**Given**: PISmart mengirimkan file PDF berupa CV, laporan keuangan, atau dokumen lain yang bukan invoice/receipt
**When**: Sistem memproses dokumen
**Then**: Respons valid dengan `doc_type = "unknown"`, semua field bernilai default (`"-"` untuk string, `0.0` untuk angka, `false` untuk boolean), `extraction_confidence = 0.0`, `requires_manual_review = true`

### Skenario 4: Dokumen Ambigu (bisa Invoice sekaligus Receipt)
**Given**: PISmart mengirimkan dokumen yang memiliki karakteristik keduanya (misal: invoice yang sudah lunas dan memuat bukti pembayaran)
**When**: Sistem tidak dapat menentukan jenis dengan pasti
**Then**: Sistem memilih klasifikasi dengan confidence lebih tinggi; jika sama, default ke `receipt`

### Skenario 5: File PDF Rusak tapi Valid Secara Format
**Given**: File memiliki magic bytes `%PDF` yang valid namun konten tidak terbaca
**When**: Sistem mencoba membaca isi
**Then**: Sistem tetap menghasilkan respons `unknown` dengan field default, tidak menolak file

## Functional Requirements

### FR-1: Klasifikasi Ulang Jenis Dokumen
Sistem harus mengklasifikasikan setiap dokumen PDF ke salah satu dari tiga jenis: `invoice`, `receipt`, atau `unknown`. Klasifikasi dilakukan tanpa memanggil AI agent (berbasis keyword dan metadata).

**Acceptance Criteria**:
- [ ] Dokumen dengan kata kunci tagihan formal (faktur, invoice, nomor faktur, VAT, PPN, tagihan) diklasifikasikan sebagai `invoice`
- [ ] Dokumen dengan kata kunci bukti bayar (e-tiket, booking confirmation, payment receipt, struk) diklasifikasikan sebagai `receipt`
- [ ] Dokumen tanpa keduanya diklasifikasikan sebagai `unknown`
- [ ] Semua nilai yang mungkin: hanya `"invoice"`, `"receipt"`, `"unknown"`

### FR-2: Agent untuk Setiap Jenis Dokumen
Sistem harus memiliki agent terpisah untuk `invoice` dan `receipt`, masing-masing dengan prompt dan skema output yang sesuai.

**Acceptance Criteria**:
- [ ] Ada agent khusus `invoice` dengan schema output berisi field tagihan formal (nomor faktur, vendor, subtotal, pajak, total)
- [ ] Ada agent khusus `receipt` dengan schema output berisi field bukti pembayaran (nomor transaksi, tanggal bayar, metode bayar, item dibeli, total)
- [ ] Setiap agent menghasilkan objek JSON yang valid sesuai skema Pydantic masing-masing

### FR-3: Penanganan Dokumen Unknown Tanpa Penolakan
Untuk dokumen bertipe `unknown`, sistem tetap menjalankan proses dan menghasilkan respons terstruktur dengan nilai default.

**Acceptance Criteria**:
- [ ] Tidak ada HTTP error (400/422) yang dikirim karena jenis dokumen tidak dikenali
- [ ] Respons `unknown` memiliki struktur Pydantic yang valid
- [ ] Semua field string bernilai `"-"`, angka `0.0`, boolean `false`, list `[]`
- [ ] `doc_type = "unknown"`
- [ ] `extraction_confidence = 0.0`
- [ ] `requires_manual_review = true`
- [ ] Field `authenticity` tetap terisi dari hasil analisis metadata PDF (tetap dijalankan)

### FR-4: Konsistensi Response Shape
Semua respons dari ketiga jenis dokumen harus memiliki envelope yang sama agar PISmart dapat memprosesnya secara seragam.

**Acceptance Criteria**:
- [ ] Field `doc_type` selalu ada di root response dengan nilai `"invoice"`, `"receipt"`, atau `"unknown"`
- [ ] Field `authenticity` selalu ada di semua jenis respons
- [ ] Field `extraction_confidence` selalu ada (0.0–1.0)
- [ ] Field `requires_manual_review` selalu ada (boolean)
- [ ] Field `summary` selalu ada (string deskripsi singkat)

### FR-5: Backward Compatibility API
Perubahan klasifikasi tidak boleh mengubah kontrak HTTP API (`/api/pinter/upload` dan `/api/pinter/extract`).

**Acceptance Criteria**:
- [ ] Request/response shape endpoint PINTER tidak berubah
- [ ] Field `data` di response `/extract` tetap berisi JSON hasil ekstraksi (beda schema per doc_type, tapi selalu ada)

## Key Entities

| Entitas | Deskripsi | Field Utama |
|---------|-----------|-------------|
| `Invoice` | Tagihan formal dari vendor | `invoice_number`, `vendor_name`, `vendor_npwp`, `issue_date`, `due_date`, `line_items`, `subtotal`, `tax`, `total_payment` |
| `Receipt` | Bukti pembayaran / konfirmasi | `receipt_number`, `transaction_date`, `payer_name`, `items_purchased`, `payment_method`, `total_payment` |
| `UnknownDocument` | Dokumen tidak teridentifikasi | semua field default, `doc_type = "unknown"` |
| `Authenticity` | Hasil analisis metadata PDF | `verdict`, `confidence_score`, `pdf_creator`, `pdf_producer`, `was_modified` |

## Success Criteria

- Setiap dokumen PDF yang diunggah menghasilkan respons JSON tanpa error, terlepas dari isinya
- Dokumen yang sebelumnya ditolak (unknown) kini menghasilkan respons bertipe `unknown` dengan `requires_manual_review = true`
- PISmart tidak perlu mengubah cara memanggil API untuk menerima manfaat klasifikasi baru
- Tidak ada regresi pada dokumen yang sebelumnya diklasifikasikan dengan benar

## Out of Scope

- Deteksi sub-tipe invoice (hotel, restoran, transportasi darat) — tetap satu agent `invoice`
- Deteksi sub-tipe receipt (pesawat, kereta, hotel) — tetap satu agent `receipt`
- OCR untuk dokumen scan / gambar (bukan PDF teks)
- Validasi isi invoice terhadap kebijakan perjalanan perusahaan
- Perubahan pada logika analisis keaslian (`authenticity`) — tetap tidak berubah

## Assumptions

- Dokumen PDF perjalanan dinas yang umum (hotel, tiket) masih memiliki kata kunci yang cukup untuk diklasifikasikan tanpa AI
- Schema `Invoice` dan `Receipt` cukup berbeda sehingga perlu agent dan prompt terpisah
- Analisis `authenticity` (metadata PDF) tetap dijalankan untuk semua jenis dokumen termasuk `unknown`
- Untuk dokumen `unknown`, sistem **tidak** memanggil AI agent — respons default langsung dikembalikan. Analisis `authenticity` dari metadata PDF tetap dijalankan (tidak membutuhkan AI).

## Dependencies

- Analisis keaslian (`authenticity`) tetap berjalan tanpa perubahan
- Endpoint PINTER (`/api/pinter/upload`, `/api/pinter/extract`) tidak berubah
- Model Pydantic baru perlu dibuat untuk `Invoice`, `Receipt`, dan `UnknownDocument`
