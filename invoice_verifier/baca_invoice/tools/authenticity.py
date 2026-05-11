from __future__ import annotations

from typing import Any

from .constants import CONFIDENCE_DEDUCTIONS, KNOWN_PROVIDERS, SOFTWARE_LABELS
from .pdf import extract_pdf_content, extract_pdf_metadata, normalize_metadata


def _do_analyze(meta: dict, full_text: str) -> dict[str, Any]:
    """Core authenticity analysis given pre-read metadata and text (no file I/O)."""
    if not meta.get("success"):
        return {
            "verdict": "MENCURIGAKAN",
            "is_suspicious": True,
            "confidence_score": 0.0,
            "detected_provider": "-",
            "pdf_creator": "-", "pdf_producer": "-",
            "creation_date": "-", "modification_date": "-",
            "was_modified": False,
            "warning_flags": ["missing_metadata"],
            "fake_evidence": [],
            "analysis_notes": f"Gagal membaca metadata: {meta.get('error', 'unknown')}",
        }

    creator = normalize_metadata(meta.get("creator") or "")
    producer = normalize_metadata(meta.get("producer") or "")
    text_lower = full_text.lower()

    warning_flags: list[str] = []
    fake_evidence: list[str] = []
    detected_sw_label: str | None = None

    # 1. Software pengeditan
    for sw, label in SOFTWARE_LABELS.items():
        if sw in creator or sw in producer:
            detected_sw_label = label
            warning_flags.append("editing_software_detected")
            fake_evidence.append(
                f"[BUKTI - SOFTWARE PENGEDITAN] "
                f"Dokumen dibuat/diedit menggunakan {label}. "
                f"Creator: '{meta.get('creator', '-')}', Producer: '{meta.get('producer', '-')}'. "
                f"Dokumen asli dari provider dicetak via sistem web "
                f"(Skia/Chrome/wkhtmltopdf), bukan software pengeditan."
            )
            break

    # 2. Identifikasi provider dari konten
    detected_provider: str | None = None
    for name, cfg in KNOWN_PROVIDERS.items():
        if any(kw in text_lower for kw in cfg["keywords"]):
            detected_provider = name
            break

    # 3. Validasi creator vs provider
    if detected_provider:
        valid_creators = KNOWN_PROVIDERS[detected_provider]["valid_creators"]
        if valid_creators:
            creator_valid = any(vc in creator or vc in producer for vc in valid_creators)
            if not creator_valid and "editing_software_detected" not in warning_flags:
                warning_flags.append("metadata_mismatch")
                fake_evidence.append(
                    f"[BUKTI - METADATA TIDAK SESUAI PROVIDER] "
                    f"Konten mengklaim dari '{detected_provider}', "
                    f"tapi creator PDF: '{meta.get('creator', '-')}'. "
                    f"Seharusnya mengandung: {', '.join(valid_creators)}."
                )
        if detected_sw_label:
            fake_evidence[0] += (
                f" Konten mengklaim dari '{detected_provider}', "
                f"namun metadata menunjukkan diproses ulang dengan {detected_sw_label}."
            )
    elif text_lower:
        warning_flags.append("unknown_provider")
        fake_evidence.append(
            f"[BUKTI - PROVIDER TIDAK DIKENAL] "
            f"Tidak ada identitas provider resmi dalam dokumen "
            f"(traveloka, tiket.com, trip.com, airasia, garuda, lion air, KAI). "
            f"Creator: '{meta.get('creator', '-')}', Producer: '{meta.get('producer', '-')}'."
        )

    # 4. Modifikasi setelah dibuat
    if meta.get("was_modified"):
        gap = meta.get("modification_gap_days")
        warning_flags.append("modified_after_creation")
        fake_evidence.append(
            f"[BUKTI - DOKUMEN DIMODIFIKASI] "
            f"Dibuat: {meta.get('creation_date', '-')}. "
            f"Dimodifikasi: {meta.get('modification_date', '-')}. "
            f"Selisih: {gap} hari. "
            f"Dokumen asli tidak dimodifikasi setelah dicetak dari sistem pemesanan."
        )

    # 5. Metadata kosong
    if not creator and not producer:
        warning_flags.append("missing_metadata")
        fake_evidence.append(
            "[BUKTI - METADATA DIHAPUS] "
            "Creator dan producer PDF kosong. "
            "Dokumen asli selalu memiliki metadata lengkap. "
            "Metadata yang hilang mengindikasikan jejak pengeditan sengaja dihapus."
        )

    confidence = round(
        max(0.0, 1.0 - sum(CONFIDENCE_DEDUCTIONS.get(f, 0.0) for f in warning_flags)), 2
    )
    is_suspicious = confidence < 0.5 or "editing_software_detected" in warning_flags
    verdict = (
        "PALSU/DIEDIT" if "editing_software_detected" in warning_flags
        else "MENCURIGAKAN" if is_suspicious
        else "AUTENTIK"
    )
    analysis_notes = (
        f"Ditemukan {len(fake_evidence)} indikator. "
        + " | ".join(e.split("]")[0].strip("[") for e in fake_evidence)
        if fake_evidence else "Tidak ditemukan indikator kecurangan."
    )

    return {
        "verdict": verdict,
        "is_suspicious": is_suspicious,
        "confidence_score": confidence,
        "detected_provider": detected_provider or "-",
        "pdf_creator": meta.get("creator") or "-",
        "pdf_producer": meta.get("producer") or "-",
        "creation_date": meta.get("creation_date") or "-",
        "modification_date": meta.get("modification_date") or "-",
        "was_modified": meta.get("was_modified", False),
        "warning_flags": warning_flags,
        "fake_evidence": fake_evidence,
        "analysis_notes": analysis_notes,
    }


def analyze_document_authenticity(file_path: str) -> dict[str, Any]:
    """
    Analisis keaslian dokumen berdasarkan metadata PDF.

    Dokumen AUTENTIK: creator/producer dari sistem web provider resmi.
    Dokumen PALSU/DIEDIT: terdeteksi software pengeditan di metadata.
    Dokumen MENCURIGAKAN: dimodifikasi setelah dibuat, atau provider tidak dikenal.

    Args:
        file_path: Path ke file PDF.

    Returns:
        dict: verdict, is_suspicious, confidence_score, fake_evidence, warning_flags, dll.
    """
    meta = extract_pdf_metadata(file_path)
    content = extract_pdf_content(file_path)
    full_text = content.get("full_text", "") if content.get("success") else ""
    return _do_analyze(meta, full_text)
