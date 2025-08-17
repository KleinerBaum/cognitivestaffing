"""Utilities for extracting text from uploaded documents."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import docx
import fitz  # PyMuPDF


def extract_text_from_file(file: Any, name: str | None = None) -> str:
    """Extract plain text from a PDF or DOCX file.

    Accepts either a Streamlit ``UploadedFile`` object or raw bytes with an
    explicit ``name``. The text is returned with empty lines removed.

    Args:
        file: Uploaded file object or raw bytes.
        name: Optional filename when ``file`` is provided as bytes.

    Returns:
        The extracted text content or an empty string on failure.
    """

    if hasattr(file, "getvalue"):
        data = file.getvalue()
        filename = getattr(file, "name", "")
    elif hasattr(file, "read"):
        data = file.read()
        filename = getattr(file, "name", "")
    else:
        data = file
        filename = name or ""
    if not data:
        return ""
    filename = filename.lower()
    text = ""
    try:
        if filename.endswith(".pdf"):
            with fitz.open(stream=data, filetype="pdf") as doc:
                text = "".join(page.get_text() for page in doc)
        elif filename.endswith(".docx") or filename.endswith(".doc"):
            document = docx.Document(BytesIO(data))
            text = "\n".join(p.text for p in document.paragraphs)
        else:
            text = data.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
