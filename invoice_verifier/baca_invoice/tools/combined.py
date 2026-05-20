from __future__ import annotations

from typing import Any

from .authenticity import analyze_authenticity
from .pdf import read_pdf


def analyze_document(file_path: str) -> dict[str, Any]:
    """Ekstrak teks DAN analisis keaslian dokumen PDF dalam satu panggilan.

    File hanya dibaca sekali. Tool ini dipakai langsung oleh `document_agent`.

    Returns:
        dict dengan key: success, full_text, total_pages, authenticity, error.
        `authenticity` berisi verdict, is_suspicious, confidence_score, dll.
    """
    content = read_pdf(file_path)
    if not content.get("success"):
        error = content.get("error", "Gagal membaca file PDF")
        return {
            "success": False,
            "error": error,
            "full_text": "",
            "total_pages": 0,
            "authenticity": analyze_authenticity({"success": False, "error": error}, ""),
        }

    full_text = content.get("full_text", "")
    meta = content.get("metadata") or {"success": False, "error": "Metadata PDF tidak tersedia"}
    return {
        "success": True,
        "file_path": file_path,
        "total_pages": content.get("total_pages", 0),
        "full_text": full_text,
        "authenticity": analyze_authenticity(meta, full_text),
    }
