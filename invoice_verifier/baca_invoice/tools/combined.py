from __future__ import annotations
from typing import Any

from .authenticity import _do_analyze
from .pdf import extract_pdf_content_and_metadata


def analyze_document(file_path: str) -> dict[str, Any]:
    """
    Ekstrak teks DAN analisis keaslian dokumen PDF dalam satu panggilan.
    File hanya dibaca sekali — lebih cepat dari memanggil dua tool terpisah.

    Args:
        file_path: Path lengkap ke file PDF.

    Returns:
        dict dengan key:
          success (bool), full_text (str), total_pages (int),
          authenticity (dict) — berisi verdict, is_suspicious, confidence_score, dll.
    """
    content = extract_pdf_content_and_metadata(file_path)
    if not content.get("success"):
        return {
            "success": False,
            "error": content.get("error", "Gagal membaca file PDF"),
            "full_text": "",
            "total_pages": 0,
            "authenticity": _do_analyze({"success": False, "error": content.get("error")}, ""),
        }

    full_text = content.get("full_text", "")
    meta = content.get("metadata") or {"success": False, "error": "Metadata PDF tidak tersedia"}
    authenticity = _do_analyze(meta, full_text)

    return {
        "success": True,
        "file_path": file_path,
        "total_pages": content.get("total_pages", 0),
        "full_text": full_text,
        "authenticity": authenticity,
    }
