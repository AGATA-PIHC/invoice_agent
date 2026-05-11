from __future__ import annotations
from pydantic import BaseModel, Field


class DocumentAuthenticity(BaseModel):
    verdict: str = "-"
    is_suspicious: bool = False
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    detected_provider: str = "-"
    pdf_creator: str = "-"
    pdf_producer: str = "-"
    creation_date: str = "-"
    modification_date: str = "-"
    was_modified: bool = False
    warning_flags: list[str] = Field(default_factory=list)
    fake_evidence: list[str] = Field(
        default_factory=list,
        description="Bukti konkret mengapa dokumen dicurigai palsu/diedit",
    )
    analysis_notes: str = "-"
