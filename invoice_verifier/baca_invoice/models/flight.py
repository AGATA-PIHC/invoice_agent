from __future__ import annotations

from pydantic import BaseModel, Field

from .authenticity import DocumentAuthenticity


class AddonItem(BaseModel):
    description: str = "-"
    price: float = 0.0


class FlightTicketResult(BaseModel):
    receipt_number: str = "-"
    po_number: str = "-"
    booking_date: str = "-"
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
    service_fee: float = 0.0
    total_payment: float = 0.0
    payment_method: str = "-"
    currency: str = "IDR"

    provider: str = "-"
    provider_company: str = "-"
    provider_npwp: str = "-"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_manual_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    summary: str = "-"
