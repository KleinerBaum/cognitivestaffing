"""Utilities to export generated text into various file formats."""

from __future__ import annotations

from io import BytesIO
import json

import docx
import fitz  # PyMuPDF


def text_to_docx(text: str) -> bytes:
    """Convert plain text into a DOCX binary."""
    doc = docx.Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def text_to_pdf(text: str) -> bytes:
    """Convert plain text into a simple single-page PDF binary."""
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
    page.insert_textbox(rect, text, fontsize=12)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def text_to_json(text: str, *, key: str, title: str | None = None) -> bytes:
    """Wrap text in a structured JSON object and return as bytes."""
    data: dict[str, str] = {"type": key, "content": text}
    if title:
        data["title"] = title
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def prepare_download_data(
    text: str, fmt: str, *, key: str, title: str | None = None
) -> tuple[bytes, str, str]:
    """Prepare data, mime type and extension for download."""
    fmt = fmt.lower()
    if fmt == "docx":
        return (
            text_to_docx(text),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if fmt == "pdf":
        return text_to_pdf(text), "application/pdf", "pdf"
    if fmt == "json":
        return text_to_json(text, key=key, title=title), "application/json", "json"
    return text.encode("utf-8"), "text/markdown", "md"
