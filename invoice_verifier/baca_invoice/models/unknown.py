from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .authenticity import DocumentAuthenticity


class UnknownResult(BaseModel):
    doc_type: Literal["unknown"] = "unknown"

    authenticity: DocumentAuthenticity = Field(default_factory=DocumentAuthenticity)

    extraction_confidence: float = 0.0
    requires_manual_review: bool = True
    review_reasons: list[str] = Field(
        default_factory=lambda: ["Dokumen tidak dikenali sebagai invoice atau receipt."]
    )
    summary: str = "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
