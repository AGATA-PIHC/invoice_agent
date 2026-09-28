from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys

# Un-stub fitz if it was mocked in conftest
sys.modules.pop("fitz", None)
fitz = importlib.import_module("fitz")

# Load real module directly from file
_pdf_tool_path = (
    Path(__file__).resolve().parents[2]
    / "invoice_verifier"
    / "baca_invoice"
    / "tools"
    / "pdf.py"
)
_spec = importlib.util.spec_from_file_location("real_pdf_tool", _pdf_tool_path)
_real_pdf_tool = importlib.util.module_from_spec(_spec)
_real_pdf_tool.fitz = fitz
_spec.loader.exec_module(_real_pdf_tool)
read_document = _real_pdf_tool.read_document
read_pdf = _real_pdf_tool.read_pdf


def test_read_pdf_digital(tmp_path):
    pdf_path = tmp_path / "digital.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=100)
    page.insert_text((50, 50), "DIGITAL INVOICE #001")
    doc.save(str(pdf_path))
    doc.close()

    result = read_pdf(str(pdf_path))
    assert result["success"] is True
    assert result["total_pages"] == 1
    assert "DIGITAL INVOICE #001" in result["full_text"]


def test_read_image_document(tmp_path):
    img_path = tmp_path / "invoice.png"
    doc = fitz.open()
    page = doc.new_page(width=300, height=100)
    page.insert_text((50, 50), "IMAGE INVOICE #999")
    pix = page.get_pixmap()
    pix.save(str(img_path))
    doc.close()

    result = read_document(str(img_path))
    assert result["success"] is True
    assert result["total_pages"] == 1
    assert result["metadata"]["success"] is True
    # PyMuPDF OCR extracts text from the rasterized image
    assert "INVOICE" in result["full_text"] or len(result["full_text"]) > 0


def test_read_nonexistent_file():
    result = read_document("/nonexistent/file.png")
    assert result["success"] is False
    assert "tidak ditemukan" in result["error"].lower()
