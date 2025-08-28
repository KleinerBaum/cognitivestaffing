import io
import re
from pathlib import Path

import requests
from requests import Response
import chardet


def _fetch_url(url: str, timeout: float = 15.0) -> str:
    """Fetch raw HTML from ``url`` with timeout and custom user agent.

    Args:
        url: HTTP(S) URL to download.
        timeout: Timeout in seconds for the request.

    Returns:
        The response body as text.

    Raises:
        AssertionError: If the URL is invalid.
        requests.RequestException: If the request fails.
    """
    assert url and re.match(r"^https?://", url), "Invalid URL"
    resp: Response = requests.get(
        url, timeout=timeout, headers={"User-Agent": "Vacalyser/1.0"}
    )
    resp.raise_for_status()
    return resp.text


def extract_text_from_url(url: str) -> str:
    """Extract readable text content from ``url``.

    Args:
        url: HTTP(S) URL.

    Returns:
        Extracted text without markup.
    """
    try:
        import trafilatura
    except ImportError:  # pragma: no cover - optional dependency
        from bs4 import BeautifulSoup

        html = _fetch_url(url)
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text("\n", strip=True)
    html = _fetch_url(url)
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    return text.strip()


def extract_text_from_file(file) -> str:
    """Extract text from an uploaded file.

    Supports PDF, DOCX and several common text formats. Unsupported binary
    files raise a ``ValueError`` so the caller can show a friendly warning.

    Args:
        file: File-like object supporting ``read`` and ``seek``.

    Returns:
        Extracted text content.

    Raises:
        ValueError: If the file is empty or has an unsupported extension.
    """
    name = getattr(file, "name", "").lower()
    data = file.read()
    file.seek(0)
    if not data:
        raise ValueError("empty file")

    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                try:
                    from pdf2image import convert_from_bytes
                    import pytesseract

                    images = convert_from_bytes(
                        data, fmt="png", first_page=idx, last_page=idx
                    )
                    ocr_text = "\n".join(
                        pytesseract.image_to_string(img) for img in images
                    )
                    page_text = (page_text + "\n" + ocr_text).strip()
                except Exception:  # pragma: no cover - optional OCR
                    page_text = page_text.strip()
            page_text = page_text.strip()
            pages.append(page_text)
        return "\n".join(pages).strip()
    if suffix == ".docx":
        import docx

        doc = docx.Document(io.BytesIO(data))
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    text_suffixes = {
        ".txt",
        ".md",
        ".rtf",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
    }
    if suffix and suffix not in text_suffixes:
        raise ValueError(f"unsupported file type: {suffix}")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        detected = chardet.detect(data)
        enc = detected["encoding"] or "utf-8"
        try:
            text = data.decode(enc, errors="ignore")
        except Exception:
            text = data.decode("utf-8", errors="ignore")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\s+$", "", text, flags=re.MULTILINE)
    return text
