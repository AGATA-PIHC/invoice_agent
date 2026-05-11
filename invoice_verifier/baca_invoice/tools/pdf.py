from __future__ import annotations
import os
import re
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


def normalize_metadata(s: str) -> str:
    """Hapus simbol ®, ™, © dan normalisasi spasi untuk pencocokan string."""
    s = s.lower()
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_pdf_content(file_path: str) -> dict[str, Any]:
    """
    Ekstrak seluruh teks dari semua halaman dokumen PDF.

    Args:
        file_path: Path ke file PDF.

    Returns:
        dict: success, total_pages, full_text, pages, error.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File tidak ditemukan: {file_path}"}
    try:
        doc = fitz.open(file_path)
        pages = [{"page": i + 1, "text": doc[i].get_text()} for i in range(len(doc))]
        full_text = "\n\n".join(f"=== HALAMAN {p['page']} ===\n{p['text']}" for p in pages)
        doc.close()
        return {"success": True, "file_path": file_path, "total_pages": len(pages),
                "full_text": full_text, "pages": pages}
    except Exception as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}


def extract_pdf_content_and_metadata(file_path: str) -> dict[str, Any]:
    """
    Ekstrak teks dan metadata PDF dengan satu kali open file.

    Returns:
        dict: success, file_path, total_pages, full_text, pages, metadata, error.
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

        full_text = "\n\n".join(f"=== HALAMAN {p['page']} ===\n{p['text']}" for p in pages)
        creation_date = _parse_pdf_date(raw_meta.get("creationDate"))
        mod_date = _parse_pdf_date(raw_meta.get("modDate"))

        was_modified = False
        modification_gap_days: int | None = None
        if creation_date and mod_date and creation_date != mod_date:
            try:
                gap_seconds = (
                    datetime.fromisoformat(mod_date) - datetime.fromisoformat(creation_date)
                ).total_seconds()
                if gap_seconds > 300:
                    was_modified = True
                    modification_gap_days = int(gap_seconds // 86400)
            except Exception:
                was_modified = False
                modification_gap_days = None

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
    except Exception as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}


def extract_pdf_metadata(file_path: str) -> dict[str, Any]:
    """
    Ekstrak metadata internal PDF (creator, producer, tanggal, dll).

    Args:
        file_path: Path ke file PDF.

    Returns:
        dict: metadata lengkap, was_modified, modification_gap_days.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File tidak ditemukan: {file_path}"}
    try:
        doc = fitz.open(file_path)
        meta = doc.metadata
        doc.close()

        creation_date = _parse_pdf_date(meta.get("creationDate"))
        mod_date = _parse_pdf_date(meta.get("modDate"))

        was_modified = False
        modification_gap_days: int | None = None
        if creation_date and mod_date and creation_date != mod_date:
            try:
                gap_seconds = (
                    datetime.fromisoformat(mod_date) - datetime.fromisoformat(creation_date)
                ).total_seconds()
                if gap_seconds > 300:
                    was_modified = True
                    modification_gap_days = int(gap_seconds // 86400)
            except Exception:
                was_modified = False
                modification_gap_days = None

        return {
            "success": True,
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creation_date": creation_date,
            "modification_date": mod_date,
            "was_modified": was_modified,
            "modification_gap_days": modification_gap_days,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
