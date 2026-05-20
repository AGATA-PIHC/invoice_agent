# Data Model: Invoice & Receipt Classification

**Phase**: 1
**Location**: `baca_invoice/models/`

## Diagram Hubungan

```
                 ┌──────────────────────────┐
                 │  DocumentAuthenticity    │  (existing, tidak berubah)
                 │  - verdict, score, ...   │
                 └────────────┬─────────────┘
                              │ used by
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌─────────▼────────┐  ┌─────────▼────────┐
│ InvoiceResult  │  │  ReceiptResult   │  │  UnknownResult   │
│ doc_type=      │  │  doc_type=       │  │  doc_type=       │
│  "invoice"     │  │   "receipt"      │  │   "unknown"      │
└────────────────┘  └──────────────────┘  └──────────────────┘
```

## 1. `DocumentAuthenticity` (existing)

Tidak berubah. Lihat [`baca_invoice/models/authenticity.py`](../../baca_invoice/models/authenticity.py).

## 2. `InvoiceResult` (BARU)

**File**: `baca_invoice/models/invoice.py`

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .authenticity import DocumentAuthenticity


class InvoiceLineItem(BaseModel):
    description: str = "-"
    quantity: float = 0.0
    unit_price: float = 0.0
    subtotal: float = 0.0


class InvoiceResult(BaseModel):
    doc_type: Literal["invoice"] = "invoice"

    # Identitas dokumen
    invoice_number: str = "-"
    issue_date: str = "-"          # tanggal terbit
    due_date: str = "-"            # tanggal jatuh tempo

    # Penjual / Vendor
    vendor_name: str = "-"
    vendor_address: str = "-"
    vendor_npwp: str = "-"
    vendor_phone: str = "-"
    vendor_email: str = "-"

    # Pembeli / Buyer
    buyer_name: str = "-"
    buyer_address: str = "-"
    buyer_npwp: str = "-"

    # Detail item
    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    # Total finansial
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0              # PPN
    total_payment: float = 0.0
    currency: str = "IDR"

    payment_terms: str = "-"      # contoh: "NET 30", "Tunai"

    # Authenticity & meta
    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
```

**Validation rules**:
- `total_payment >= 0` (Pydantic akan validate via Field constraint kalau perlu)
- `extraction_confidence ∈ [0.0, 1.0]`
- `currency` default "IDR" (untuk dokumen Indonesia)

## 3. `ReceiptResult` (BARU)

**File**: `baca_invoice/models/receipt.py`

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .authenticity import DocumentAuthenticity


class ReceiptItem(BaseModel):
    description: str = "-"
    quantity: float = 0.0
    price: float = 0.0


class ReceiptResult(BaseModel):
    doc_type: Literal["receipt"] = "receipt"

    # Identitas transaksi
    receipt_number: str = "-"
    transaction_date: str = "-"
    payment_date: str = "-"

    # Penjual / Merchant
    merchant_name: str = "-"
    merchant_address: str = "-"
    merchant_phone: str = "-"

    # Pembayar
    payer_name: str = "-"
    payer_email: str = "-"
    payer_phone: str = "-"

    # Detail item yang dibeli
    items_purchased: list[ReceiptItem] = Field(default_factory=list)

    # Total
    subtotal: float = 0.0
    tax: float = 0.0
    service_fee: float = 0.0
    total_payment: float = 0.0
    currency: str = "IDR"

    # Pembayaran
    payment_method: str = "-"     # tunai, kartu, transfer, dll
    payment_status: str = "-"     # paid, pending

    # Authenticity & meta
    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
```

## 4. `UnknownResult` (BARU)

**File**: `baca_invoice/models/unknown.py`

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from .authenticity import DocumentAuthenticity


class UnknownResult(BaseModel):
    doc_type: Literal["unknown"] = "unknown"

    # Authenticity TETAP terisi dari analisis metadata
    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)

    # Selalu 0.0 — tidak ada ekstraksi yang dilakukan
    extraction_confidence: float = 0.0

    # Selalu True — operator manusia harus cek
    requires_manual_review: bool = True

    # Berisi alasan kenapa diklasifikasikan unknown
    review_reasons: list[str] = Field(
        default_factory=lambda: ["Dokumen tidak dikenali sebagai invoice atau receipt."]
    )

    # Pesan deskriptif singkat
    summary: str = "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
```

## 5. State Transitions

```
PDF upload received
        │
        ▼
classify_document(filename, file_path)
        │
        ├──► "invoice" ──► InvoiceAgent → InvoiceResult → DB
        │
        ├──► "receipt" ──► ReceiptAgent → ReceiptResult → DB
        │
        └──► "unknown" ──► analyze_document_authenticity (no AI)
                              │
                              └─► UnknownResult(authenticity=..., defaults) → DB
```

## 6. Migration & Cleanup

File yang **dihapus** setelah implementasi:
- `baca_invoice/models/flight.py` → `FlightTicketResult` digantikan oleh `ReceiptResult`
- `baca_invoice/models/hotel.py` → `HotelInvoiceResult` digantikan oleh `InvoiceResult`

File `baca_invoice/models/__init__.py` di-update:

```python
from .authenticity import DocumentAuthenticity
from .invoice import InvoiceResult, InvoiceLineItem
from .receipt import ReceiptResult, ReceiptItem
from .unknown import UnknownResult

__all__ = [
    "DocumentAuthenticity",
    "InvoiceResult", "InvoiceLineItem",
    "ReceiptResult", "ReceiptItem",
    "UnknownResult",
]
```

## 7. Validasi terhadap Spec

| Spec FR | Model yang memenuhi | Cara |
|---------|---------------------|------|
| FR-1: Klasifikasi 3 jenis | `doc_type` Literal pada tiap model | Pydantic Literal type enforce nilai |
| FR-2: Agent terpisah | `InvoiceResult` & `ReceiptResult` punya field beda | Schema berbeda → prompt berbeda |
| FR-3: Unknown tanpa penolakan | `UnknownResult` valid Pydantic | Semua field punya default; bisa di-construct tanpa argumen |
| FR-4: Konsistensi response | `doc_type`, `authenticity`, `extraction_confidence`, `requires_manual_review`, `summary` ada di semua model | Common fields explicit di tiap model |
| FR-5: Backward compat | Schema hanya berubah di field `data`, envelope `trx_id/status/message` tetap | Lihat contracts/pinter-api.md |
