from __future__ import annotations

from baca_invoice.models.travel_document import InvoiceLineItem, ReceiptItem, TravelDocumentResult
from baca_invoice.models.unknown import UnknownResult


def test_invoice_line_item_defaults():
    item = InvoiceLineItem()
    assert item.description == "-"
    assert item.quantity == 0.0
    assert item.unit_price == 0.0
    assert item.subtotal == 0.0


def test_receipt_item_defaults():
    item = ReceiptItem()
    assert item.description == "-"
    assert item.quantity == 0.0
    assert item.price == 0.0


def test_travel_document_invoice_defaults():
    result = TravelDocumentResult(doc_type="invoice", document_subtype="hotel")
    assert result.doc_type == "invoice"
    assert result.document_subtype == "hotel"
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


def test_travel_document_receipt_with_items():
    result = TravelDocumentResult(
        doc_type="receipt",
        document_subtype="flight",
        receipt_number="TRX-123",
        merchant_name="Garuda Indonesia",
        total_payment=1275000.0,
        items_purchased=[ReceiptItem(description="Tiket CGK-DPS", quantity=1, price=1250000)],
    )
    assert result.receipt_number == "TRX-123"
    assert len(result.items_purchased) == 1
    assert result.items_purchased[0].price == 1250000.0


def test_travel_document_line_items():
    result = TravelDocumentResult(
        doc_type="invoice",
        document_subtype="hotel",
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


def test_travel_document_string_normalization():
    result = TravelDocumentResult(
        doc_type="invoice",
        document_subtype="hotel",
        facilities=["wifi", "gym"],
    )
    assert result.facilities == "wifi, gym"


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
    a = UnknownResult()
    b = UnknownResult()
    a.review_reasons.append("extra")
    assert len(b.review_reasons) == 1
