from __future__ import annotations

from typing import Any

from baca_invoice.models.travel_document import TravelDocumentResult

_DOC_TYPES = {"invoice", "receipt", "unknown"}
_SUB_TYPES = {"hotel", "flight", "unknown"}

_EMPTY_STRINGS = {"", "-", "-  ", "n/a", "none", "null", "tidak ada", "not available"}

_NON_TRAVEL_DOC_MARKERS = (
    "not an invoice",
    "not a receipt",
    "not invoice",
    "not receipt",
    "not an invoice/receipt",
    "not invoice/receipt",
    "bukan invoice",
    "bukan receipt",
    "bukan faktur",
    "bukan struk",
    "bukan kwitansi",
    "technical guide",
    "panduan",
    "guidance",
)

_INVOICE_EVIDENCE_FIELDS = (
    "invoice_number",
    "issue_date",
    "due_date",
    "vendor_name",
    "vendor_npwp",
    "buyer_name",
    "payment_terms",
    "provider",
    "provider_company",
)
_RECEIPT_EVIDENCE_FIELDS = (
    "receipt_number",
    "transaction_date",
    "payment_date",
    "merchant_name",
    "payer_name",
    "payment_status",
    "provider",
    "provider_company",
)
_HOTEL_EVIDENCE_FIELDS = (
    "order_id",
    "booking_date",
    "hotel_name",
    "check_in_date",
    "check_out_date",
)
_FLIGHT_EVIDENCE_FIELDS = (
    "po_number",
    "transaction_status",
    "traveler_name",
    "airline",
    "route_from",
    "route_to",
    "flight_date",
)
_AMOUNT_FIELDS = ("subtotal", "tax", "service_fee", "total_payment")


def validate_agent_result(result: dict) -> dict:
    """Validasi & normalisasi hasil agent, lalu coerce ke TravelDocumentResult.

    Jika agent mengklaim doc_type=invoice/receipt namun summary/review_reasons
    menunjukkan dokumen non-travel TANPA evidence field, klaim itu di-override
    menjadi unknown agar tidak ada false positive.
    """
    if not isinstance(result, dict) or set(result) == {"raw"}:
        raise ValueError("Agent did not return a valid JSON object matching the expected schema.")

    doc_type = _normalize_choice(result.get("doc_type"), _DOC_TYPES)
    sub_type = _normalize_choice(result.get("document_subtype"), _SUB_TYPES)

    if doc_type == "unknown" or _agent_rejects_claimed_doc_type(result, doc_type, sub_type):
        result = _mark_unknown_result(result)
    else:
        result["doc_type"] = doc_type
        result["document_subtype"] = sub_type

    return TravelDocumentResult.model_validate(result).model_dump()


def _normalize_choice(value: Any, allowed: set[str]) -> str:
    normalized = str(value or "unknown").strip().lower()
    return normalized if normalized in allowed else "unknown"


def _agent_rejects_claimed_doc_type(result: dict, doc_type: str, sub_type: str) -> bool:
    if doc_type not in ("invoice", "receipt"):
        return False

    text_parts = [str(result.get("summary") or "")]
    text_parts.extend(str(item) for item in result.get("review_reasons") or [])
    joined_text = " ".join(text_parts).lower()
    if not any(marker in joined_text for marker in _NON_TRAVEL_DOC_MARKERS):
        return False

    evidence_fields = list(
        _INVOICE_EVIDENCE_FIELDS if doc_type == "invoice" else _RECEIPT_EVIDENCE_FIELDS
    )
    if sub_type == "hotel":
        evidence_fields.extend(_HOTEL_EVIDENCE_FIELDS)
    elif sub_type == "flight":
        evidence_fields.extend(_FLIGHT_EVIDENCE_FIELDS)

    has_document_evidence = any(_has_value(result.get(field)) for field in evidence_fields)
    has_amount_evidence = any(_has_value(result.get(field)) for field in _AMOUNT_FIELDS)
    return not has_document_evidence and not has_amount_evidence


def _mark_unknown_result(result: dict) -> dict:
    result = dict(result)
    result["doc_type"] = "unknown"
    result["document_subtype"] = "unknown"
    result["extraction_confidence"] = 0.0
    result["requires_manual_review"] = True

    authenticity = dict(result.get("authenticity") or {})
    authenticity["verdict"] = "TIDAK DIVERIFIKASI"
    authenticity["is_suspicious"] = False
    authenticity["confidence_score"] = 0.0
    authenticity["analysis_notes"] = (
        "Dokumen tidak dikenali sebagai invoice atau receipt perjalanan dinas. "
        "Analisis keaslian tidak dilakukan."
    )
    result["authenticity"] = authenticity

    review_reasons = list(result.get("review_reasons") or [])
    reason = "Dokumen tidak dikenali sebagai invoice atau receipt."
    if reason not in review_reasons:
        review_reasons.insert(0, reason)
    result["review_reasons"] = review_reasons

    if not _has_value(result.get("summary")):
        result["summary"] = "Dokumen tidak terklasifikasi. Tidak ada data yang diekstraksi."
    return result


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _EMPTY_STRINGS
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, list):
        return bool(value)
    return bool(value)
