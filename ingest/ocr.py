"""OCR utilities for PDF processing."""

from __future__ import annotations

from io import BytesIO
from typing import Callable

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


def ocr_pdf_openai(pdf_path: str) -> str:
    """OCR using OpenAI Vision (placeholder).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Recognised text.
    """

    raise NotImplementedError("OpenAI Vision OCR is not implemented in tests")


def ocr_pdf_textract(pdf_path: str) -> str:
    """OCR using AWS Textract (placeholder)."""

    raise NotImplementedError("AWS Textract OCR is not implemented in tests")


def ocr_pdf_rapid(pdf_path: str) -> str:
    """OCR using RapidOCR (placeholder)."""

    raise NotImplementedError("RapidOCR OCR is not implemented in tests")


def select_ocr_backend(name: str) -> Callable[[str], str]:
    """Return the OCR function for ``name``.

    Supported names: ``tesseract`` (default), ``openai``, ``textract``, ``rapidocr``.
    """

    mapping: dict[str, Callable[[str], str]] = {
        "tesseract": ocr_pdf,
        "openai": ocr_pdf_openai,
        "textract": ocr_pdf_textract,
        "rapidocr": ocr_pdf_rapid,
    }
    key = (name or "tesseract").lower()
    if key not in mapping:
        raise ValueError(f"Unknown OCR backend: {name}")
    return mapping[key]
