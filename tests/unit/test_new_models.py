from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Stub heavy deps before importing models
for _mod in ("fitz", "google", "google.adk", "baca_invoice.tools", "baca_invoice.tools.constants"):
    sys.modules.setdefault(_mod, MagicMock())

from baca_invoice.models.invoice import InvoiceLineItem, InvoiceResult  # noqa: E402
from baca_invoice.models.receipt import ReceiptItem, ReceiptResult  # noqa: E402
from baca_invoice.models.unknown import UnknownResult  # noqa: E402

# ── InvoiceLineItem ───────────────────────────────────────────────────────────

def test_invoice_line_item_defaults():
    item = InvoiceLineItem()
    assert item.description == "-"
    assert item.quantity == 0.0
    assert item.unit_price == 0.0
    assert item.subtotal == 0.0


# ── InvoiceResult ─────────────────────────────────────────────────────────────

def test_invoice_result_doc_type_literal():
    result = InvoiceResult()
    assert result.doc_type == "invoice"


def test_invoice_result_defaults():
    result = InvoiceResult()
    assert result.invoice_number == "-"
    assert result.vendor_name == "-"
    assert result.buyer_name == "-"
    assert result.line_items == []
    assert result.subtotal == 0.0
    assert result.tax == 0.0
    assert result.total_payment == 0.0
    assert result.currency == "IDR"
    assert result.extraction_confidence == 0.0
    assert result.requires_manual_review is False
    assert result.review_reasons == []
    assert result.summary == "-"


def test_invoice_result_doc_type_cannot_be_changed():
    result = InvoiceResult(doc_type="invoice")
    assert result.doc_type == "invoice"


def test_invoice_result_extraction_confidence_bounds():
    result = InvoiceResult(extraction_confidence=0.85)
    assert result.extraction_confidence == 0.85


def test_invoice_result_with_line_items():
    result = InvoiceResult(
        invoice_number="INV-001",
        vendor_name="PT Hotel Indah",
        total_payment=1887000.0,
        line_items=[
            InvoiceLineItem(
                description="Kamar Deluxe", quantity=2, unit_price=850000, subtotal=1700000
            )
        ],
    )
    assert result.invoice_number == "INV-001"
    assert len(result.line_items) == 1
    assert result.line_items[0].subtotal == 1700000.0


# ── ReceiptItem ───────────────────────────────────────────────────────────────

def test_receipt_item_defaults():
    item = ReceiptItem()
    assert item.description == "-"
    assert item.quantity == 0.0
    assert item.price == 0.0


# ── ReceiptResult ─────────────────────────────────────────────────────────────

def test_receipt_result_doc_type_literal():
    result = ReceiptResult()
    assert result.doc_type == "receipt"


def test_receipt_result_defaults():
    result = ReceiptResult()
    assert result.receipt_number == "-"
    assert result.merchant_name == "-"
    assert result.payer_name == "-"
    assert result.items_purchased == []
    assert result.subtotal == 0.0
    assert result.service_fee == 0.0
    assert result.total_payment == 0.0
    assert result.currency == "IDR"
    assert result.payment_method == "-"
    assert result.payment_status == "-"
    assert result.extraction_confidence == 0.0
    assert result.requires_manual_review is False


def test_receipt_result_with_items():
    result = ReceiptResult(
        receipt_number="TRX-123",
        merchant_name="Garuda Indonesia",
        total_payment=1275000.0,
        items_purchased=[ReceiptItem(description="Tiket CGK→DPS", quantity=1, price=1250000)],
    )
    assert result.receipt_number == "TRX-123"
    assert len(result.items_purchased) == 1
    assert result.items_purchased[0].price == 1250000.0


# ── UnknownResult ─────────────────────────────────────────────────────────────

def test_unknown_result_doc_type_literal():
    result = UnknownResult()
    assert result.doc_type == "unknown"


def test_unknown_result_defaults():
    result = UnknownResult()
    assert result.extraction_confidence == 0.0
    assert result.requires_manual_review is True
    assert len(result.review_reasons) == 1
    reason = result.review_reasons[0].lower()
    assert "invoice" in reason or "unknown" in reason
    assert result.summary != ""


def test_unknown_result_review_reasons_independent():
    """Each UnknownResult instance has its own list (no shared mutable default)."""
    a = UnknownResult()
    b = UnknownResult()
    a.review_reasons.append("extra")
    assert len(b.review_reasons) == 1
