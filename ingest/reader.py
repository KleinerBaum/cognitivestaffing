"""Read job text from multiple sources."""

from __future__ import annotations

import re
from pathlib import Path
import os

import fitz  # type: ignore[import-not-found]
from bs4 import BeautifulSoup
from docx import Document
import requests

from .ocr import select_ocr_backend

OCR_BACKEND = os.getenv("OCR_BACKEND", "tesseract")


def _clean(text: str) -> str:
    """Collapse whitespace and strip surrounding spaces."""

    return re.sub(r"\s+", " ", text).strip()


def _read_txt(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def _read_docx(path: Path) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def _read_pdf(path: Path) -> str:
    with fitz.open(path) as doc:
        return "".join(page.get_text() for page in doc)


def _read_url(url: str) -> str:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text(" ")


def read_job_text(
    files: list[str],
    url: str | None = None,
    pasted: str | None = None,
    *,
    use_ocr: bool = False,
    ocr_backend: str = OCR_BACKEND,
) -> str:
    """Merge text from files, URL and pasted snippets.

    Args:
        files: Paths to local files (PDF, DOCX, TXT).
        url: Optional web URL to fetch.
        pasted: Additional pasted text.
        use_ocr: Whether to OCR PDFs lacking extractable text.
        ocr_backend: Which OCR service to use if ``use_ocr`` is true.

    Returns:
        Cleaned and de-duplicated text.
    """

    texts: list[str] = []
    for name in files:
        path = Path(name)
        suffix = path.suffix.lower()
        content = ""
        if suffix == ".pdf":
            content = _read_pdf(path)
            if use_ocr and not content.strip():
                ocr_func = select_ocr_backend(ocr_backend)
                content = ocr_func(str(path))
        elif suffix == ".docx":
            content = _read_docx(path)
        elif suffix == ".txt":
            content = _read_txt(path)
        if content:
            texts.append(content)

    if url:
        texts.append(_read_url(url))
    if pasted:
        texts.append(pasted)

    cleaned = [_clean(t) for t in texts if t]
    unique = list(dict.fromkeys(cleaned))
    return "\n".join(unique)
