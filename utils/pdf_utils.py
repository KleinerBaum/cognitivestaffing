"""Utilities for extracting text from uploaded documents."""

from __future__ import annotations

import io
from typing import BinaryIO

import fitz  # PyMuPDF
from docx import Document


def extract_text_from_file(uploaded_file: BinaryIO) -> str:
    """Return text content from an uploaded PDF or DOCX file.

    Args:
        uploaded_file: A file-like object with ``name`` and ``read``
            attributes, such as a Streamlit ``UploadedFile``.

    Returns:
        The extracted plain text.

    Raises:
        ValueError: If the file type is unsupported or parsing fails.
    """

    name = (getattr(uploaded_file, "name", "") or "").lower()
    data = uploaded_file.read()
    try:
        if name.endswith(".pdf"):
            with fitz.open(stream=data, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        if name.endswith(".docx"):
            bio = io.BytesIO(data)
            doc = Document(bio)
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:  # pragma: no cover - passthrough to caller
        raise ValueError("Failed to parse document") from exc
    raise ValueError("Unsupported file type")
