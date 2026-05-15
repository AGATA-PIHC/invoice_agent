from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TravelSubmitRequest(BaseModel):
    document_type: Literal["invoice", "receipt"] = Field(
        ...,
        description="invoice = tagihan (belum dibayar), receipt = bukti bayar",
    )
    source_system: str = Field(..., description="Nama sistem pengirim, e.g. 'PISmart'")
    reference_id: str = Field(..., description="ID referensi dari sistem pengirim")
    filename: str = Field(..., description="Nama file PDF, harus berakhiran .pdf")
    file_base64: str = Field(..., description="Isi file PDF di-encode base64")


class TravelSubmitResponse(BaseModel):
    transaction_id: str
    reference_id: str
    status: str
    submitted_at: datetime


class TravelResultResponse(BaseModel):
    transaction_id: str
    reference_id: str
    document_type: str
    status: str
    ocr_confidence: float | None = Field(
        None,
        description="Confidence level OCR 0.0–1.0. None jika belum selesai.",
    )
    result: dict | None = None
    warning: str | None = None
    error: str | None = None
    completed_at: datetime | None = None
