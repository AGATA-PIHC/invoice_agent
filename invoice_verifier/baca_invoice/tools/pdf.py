from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import fitz


def _parse_pdf_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        cleaned = raw.replace("D:", "").strip()[:14]
        return datetime.strptime(cleaned, "%Y%m%d%H%M%S").isoformat()
    except Exception:
        return raw or None


def _compute_modification_info(
    creation_date: str | None, mod_date: str | None
) -> tuple[bool, int | None]:
    if not (creation_date and mod_date and creation_date != mod_date):
        return False, None
    try:
        gap_seconds = (
            datetime.fromisoformat(mod_date) - datetime.fromisoformat(creation_date)
        ).total_seconds()
    except Exception:
        return False, None
    if gap_seconds <= 300:
        return False, None
    return True, int(gap_seconds // 86400)


def read_pdf(file_path: str) -> dict[str, Any]:
    """Baca seluruh teks dan metadata PDF dalam satu kali open file.

    Returns:
        dict dengan key:
          success, file_path, total_pages, full_text, pages, metadata, error.
        `metadata` berisi: title, author, creator, producer, creation_date,
        modification_date, was_modified, modification_gap_days.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File tidak ditemukan: {file_path}"}
    try:
        doc = fitz.open(file_path)
        try:
            raw_meta = doc.metadata
            pages = [{"page": i + 1, "text": doc[i].get_text()} for i in range(len(doc))]
        finally:
            doc.close()
    except Exception as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    full_text = "\n\n".join(f"=== HALAMAN {p['page']} ===\n{p['text']}" for p in pages)
    creation_date = _parse_pdf_date(raw_meta.get("creationDate"))
    mod_date = _parse_pdf_date(raw_meta.get("modDate"))
    was_modified, modification_gap_days = _compute_modification_info(creation_date, mod_date)

    metadata = {
        "success": True,
        "title": raw_meta.get("title", ""),
        "author": raw_meta.get("author", ""),
        "creator": raw_meta.get("creator", ""),
        "producer": raw_meta.get("producer", ""),
        "creation_date": creation_date,
        "modification_date": mod_date,
        "was_modified": was_modified,
        "modification_gap_days": modification_gap_days,
    }
    return {
        "success": True,
        "file_path": file_path,
        "total_pages": len(pages),
        "full_text": full_text,
        "pages": pages,
        "metadata": metadata,
    }
