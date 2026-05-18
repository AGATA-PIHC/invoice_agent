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

    receipt_number: str = "-"
    transaction_date: str = "-"
    payment_date: str = "-"

    merchant_name: str = "-"
    merchant_address: str = "-"
    merchant_phone: str = "-"

    payer_name: str = "-"
    payer_email: str = "-"
    payer_phone: str = "-"

    items_purchased: list[ReceiptItem] = Field(default_factory=list)

    subtotal: float = 0.0
    tax: float = 0.0
    service_fee: float = 0.0
    total_payment: float = 0.0
    currency: str = "IDR"

    payment_method: str = "-"
    payment_status: str = "-"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
