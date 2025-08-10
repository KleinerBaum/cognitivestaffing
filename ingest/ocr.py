"""OCR utilities for PDF processing."""

from __future__ import annotations

from io import BytesIO

import fitz  # type: ignore[import-not-found]
from PIL import Image
import pytesseract


def ocr_pdf(pdf_path: str) -> str:
    """Extract text from a PDF using Tesseract OCR.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Text recognised from the PDF.
    """

    text_parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap()
            img = Image.open(BytesIO(pix.tobytes("png")))
            text_parts.append(pytesseract.image_to_string(img))
    return "\n".join(text_parts).strip()
