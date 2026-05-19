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

    invoice_number: str = "-"
    issue_date: str = "-"
    due_date: str = "-"

    vendor_name: str = "-"
    vendor_address: str = "-"
    vendor_npwp: str = "-"
    vendor_phone: str = "-"
    vendor_email: str = "-"

    buyer_name: str = "-"
    buyer_address: str = "-"
    buyer_npwp: str = "-"

    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total_payment: float = 0.0
    currency: str = "IDR"

    payment_terms: str = "-"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
