"""OCR utilities for PDF processing."""

from __future__ import annotations

import fitz

from core.ocr_backends import extract_text as ocr_extract_text


def ocr_pdf(pdf_path: str) -> str:
    """Extract text from a PDF using OpenAI Vision.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Text recognised from the PDF.
    """
    text_parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap()
            text_parts.append(ocr_extract_text(pix.tobytes("png")))
    return "\n".join(text_parts).strip()
