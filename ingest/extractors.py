import io
import re
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
    """Extract text from an uploaded file (PDF, DOCX, or TXT).

    Args:
        file: File-like object supporting ``read`` and ``seek``.

    Returns:
        Extracted text content.
    """
    name = getattr(file, "name", "").lower()
    data = file.read()
    file.seek(0)
    if not data:
        return ""
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join([p.extract_text() or "" for p in reader.pages]).strip()
    if name.endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(data))
        return "\n".join([p.text for p in doc.paragraphs]).strip()
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
