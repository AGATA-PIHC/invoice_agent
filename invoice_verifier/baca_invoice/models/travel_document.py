from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .authenticity import DocumentAuthenticity


class InvoiceLineItem(BaseModel):
    description: str = "-"
    quantity: float = 0.0
    unit_price: float = 0.0
    subtotal: float = 0.0


class ReceiptItem(BaseModel):
    description: str = "-"
    quantity: float = 0.0
    price: float = 0.0


class AddonItem(BaseModel):
    description: str = "-"
    price: float = 0.0


class TravelDocumentResult(BaseModel):
    doc_type: Literal["invoice", "receipt", "unknown"] = "unknown"
    document_subtype: Literal["general", "hotel", "flight", "unknown"] = "general"

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
    payment_terms: str = "-"

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
    payment_status: str = "-"

    order_id: str = "-"
    order_detail_id: str = "-"
    booking_date: str = "-"
    booker_name: str = "-"
    booker_email: str = "-"
    booker_phone: str = "-"
    hotel_name: str = "-"
    hotel_address: str = "-"
    hotel_city: str = "-"
    hotel_phone: str = "-"
    room_type: str = "-"
    total_rooms: int = 0
    room_capacity: str = "-"
    check_in_date: str = "-"
    check_in_time: str = "-"
    check_out_date: str = "-"
    check_out_time: str = "-"
    total_nights: int = 0
    breakfast_included: bool = False
    facilities: str = "-"
    special_requests: str = "-"

    po_number: str = "-"
    transaction_status: str = "-"
    traveler_name: str = "-"
    traveler_email: str = "-"
    traveler_phone: str = "-"
    airline: str = "-"
    route_from: str = "-"
    route_to: str = "-"
    flight_date: str = "-"
    seat_class: str = "-"
    passenger_type: str = "-"
    ticket_price: float = 0.0
    addons: list[AddonItem] = Field(default_factory=list)

    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    service_fee: float = 0.0
    total_payment: float = 0.0
    payment_method: str = "-"
    payment_date_time: str = "-"
    currency: str = "IDR"

    provider: str = "-"
    provider_company: str = "-"
    provider_address: str = "-"
    provider_npwp: str = "-"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"

    @field_validator(
        "doc_type",
        "document_subtype",
        "invoice_number",
        "issue_date",
        "due_date",
        "vendor_name",
        "vendor_address",
        "vendor_npwp",
        "vendor_phone",
        "vendor_email",
        "buyer_name",
        "buyer_address",
        "buyer_npwp",
        "payment_terms",
        "receipt_number",
        "transaction_date",
        "payment_date",
        "merchant_name",
        "merchant_address",
        "merchant_phone",
        "payer_name",
        "payer_email",
        "payer_phone",
        "payment_status",
        "order_id",
        "order_detail_id",
        "booking_date",
        "booker_name",
        "booker_email",
        "booker_phone",
        "hotel_name",
        "hotel_address",
        "hotel_city",
        "hotel_phone",
        "room_type",
        "room_capacity",
        "check_in_date",
        "check_in_time",
        "check_out_date",
        "check_out_time",
        "facilities",
        "special_requests",
        "po_number",
        "transaction_status",
        "traveler_name",
        "traveler_email",
        "traveler_phone",
        "airline",
        "route_from",
        "route_to",
        "flight_date",
        "seat_class",
        "passenger_type",
        "payment_method",
        "payment_date_time",
        "currency",
        "provider",
        "provider_company",
        "provider_address",
        "provider_npwp",
        "summary",
        mode="before",
    )
    @classmethod
    def normalize_string_fields(cls, value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item not in (None, ""))
        if isinstance(value, dict):
            return str(value)
        return str(value)
