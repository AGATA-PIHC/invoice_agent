from __future__ import annotations
from pydantic import BaseModel, Field
from .authenticity import DocumentAuthenticity


class HotelInvoiceResult(BaseModel):
    order_id: str = "-"
    order_detail_id: str = "-"
    booking_date: str = "-"
    payment_date: str = "-"

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

    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total_payment: float = 0.0
    payment_method: str = "-"
    payment_date_time: str = "-"
    currency: str = "IDR"

    provider: str = "-"
    provider_company: str = "-"
    provider_address: str = "-"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
