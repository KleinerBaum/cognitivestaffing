import io
import inspect
import logging
import re
from urllib.parse import urljoin
from pathlib import Path
from typing import Any, Iterable

import chardet
import requests
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from requests import Response

from .types import ContentBlock, StructuredDocument, build_plain_text_document


logger = logging.getLogger(__name__)


_REDIRECT_STATUSES = {301, 302, 307, 308}


def _fetch_url(url: str, timeout: float = 15.0) -> str:
    """Fetch raw HTML from ``url`` with timeout and custom user agent.

    Args:
        url: HTTP(S) URL to download.
        timeout: Timeout in seconds for the request.

    Returns:
        The response body as text.

    Raises:
        ValueError: If the URL is invalid or cannot be fetched.
    """
    if not url or not re.match(r"^https?://", url):
        raise ValueError("Invalid URL")
    # ``requests`` already protects against infinite redirect loops with its
    # built-in limit (currently 30). Some environments, however, bypass that
    # behaviour or surface redirects via ``raise_for_status``. Keep a generous
    # manual cap so we can follow longer but finite redirect chains ourselves.
    remaining_redirects = 15
    current_url = url
    redirect_kwargs: dict[str, Any] = {}
    try:
        signature = inspect.signature(requests.get)
    except (TypeError, ValueError):  # pragma: no cover - fallback for C extensions
        signature = None
    if signature is None:
        redirect_kwargs = {"allow_redirects": True}
    else:
        params = signature.parameters.values()
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params) or "allow_redirects" in signature.parameters:
            redirect_kwargs = {"allow_redirects": True}
    while True:
        try:
            resp: Response = requests.get(
                current_url,
                timeout=timeout,
                headers={"User-Agent": "CognitiveNeeds/1.0"},
                **redirect_kwargs,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:  # pragma: no cover - network
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            headers = getattr(response, "headers", {}) or {}
            location = None
            if hasattr(headers, "get"):
                location = headers.get("Location") or headers.get("location")
            elif isinstance(headers, dict):
                location = headers.get("Location") or headers.get("location")
            if (
                status in _REDIRECT_STATUSES
                and location
                and remaining_redirects > 0
            ):
                remaining_redirects -= 1
                previous_url = current_url
                current_url = urljoin(previous_url, location)
                logger.debug(
                    "Redirecting fetch from %s to %s (remaining=%s)",
                    previous_url,
                    current_url,
                    remaining_redirects,
                )
                continue
            if status in _REDIRECT_STATUSES and location:
                logger.warning("Redirect limit exceeded for %s", url)
                raise ValueError("too many redirects while fetching URL") from exc
            status_display = status if status is not None else "unknown"
            logger.warning("Failed to fetch %s (status %s)", current_url, status_display)
            raise ValueError(f"failed to fetch URL (status {status_display})") from exc


def extract_text_from_url(url: str) -> StructuredDocument:
    """Extract readable text content from ``url``.

    Args:
        url: HTTP(S) URL.

    Returns:
        Extracted text without markup.

    Raises:
        ValueError: If no text could be extracted.
    """
    html = _fetch_url(url)
    blocks = _parse_html_blocks(html)
    text = ""
    if blocks:
        text = StructuredDocument.from_blocks(blocks, source=url).text
    if not text:
        try:
            import trafilatura
        except ImportError:  # pragma: no cover - optional dependency
            text = ""
        else:
            text = (
                trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                )
                or ""
            )
    if not text:
        raise ValueError("URL contains no extractable text")
    if not blocks:
        return build_plain_text_document(text, source=url)
    doc = StructuredDocument.from_blocks(blocks, source=url)
    if not doc.text:
        return build_plain_text_document(text, source=url)
    return doc


def extract_text_from_file(file) -> StructuredDocument:
    """Extract text from an uploaded file.

    Supports PDF, DOCX and several common text formats. Unsupported binary
    files raise a ``ValueError`` so the caller can show a friendly warning.

    Args:
        file: File-like object supporting ``read`` and ``seek``.

    Returns:
        Extracted text content.

    Raises:
        ValueError: If the file is empty, too large or has an unsupported
            extension. ``RuntimeError`` is raised when OCR dependencies are
            missing for scanned PDFs.
    """
    name = getattr(file, "name", "").lower()
    data = file.read()
    file.seek(0)
    if not data:
        raise ValueError("empty file")

    if len(data) > 20 * 1024 * 1024:
        raise ValueError("file too large")

    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(io.BytesIO(data), name)
    if suffix == ".docx":
        return _extract_docx(io.BytesIO(data), name)
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
    return build_plain_text_document(text, source=name)


def _iter_block_items(doc: Any) -> Iterable[Paragraph | Table]:
    """Yield paragraphs and tables in document order."""

    body: Any = getattr(doc, "_body", None)
    if body is None:
        return []
    iterator = getattr(body, "iter_inner_content", None)
    if not callable(iterator):
        return []
    items: list[Paragraph | Table] = []
    for child in iterator():  # pragma: no cover - exercised via docx parsing
        if isinstance(child, (Paragraph, Table)):
            items.append(child)
        else:
            tag = getattr(getattr(child, "_element", None), "tag", "")
            if isinstance(tag, str) and tag.endswith("}p"):
                items.append(Paragraph(child, doc))
            elif isinstance(tag, str) and tag.endswith("}tbl"):
                items.append(Table(child, doc))
    return items


def _paragraph_is_list(paragraph: Paragraph) -> bool:
    props = getattr(paragraph._p, "pPr", None)
    if props is None:
        return False
    num_pr = getattr(props, "numPr", None)
    return num_pr is not None


def _paragraph_list_level(paragraph: Paragraph) -> int:
    props = getattr(paragraph._p, "pPr", None)
    if props is None:
        return 0
    num_pr = getattr(props, "numPr", None)
    if num_pr is None:
        return 0
    level = getattr(getattr(num_pr, "ilvl", None), "val", None)
    try:
        return int(level) if level is not None else 0
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0


def _paragraph_list_type(paragraph: Paragraph) -> str:
    style_name = (paragraph.style.name if paragraph.style else "").lower()
    if "number" in style_name or "zähl" in style_name:
        return "ordered"
    if "bullet" in style_name or "aufzähl" in style_name:
        return "unordered"
    return "unordered"


def _heading_level(paragraph: Paragraph) -> int | None:
    style_name = paragraph.style.name if paragraph.style else ""
    match = re.search(r"(Heading|Überschrift)\s*(\d)", style_name)
    if match:
        try:
            return int(match.group(2))
        except ValueError:  # pragma: no cover - defensive
            return None
    return None


def _extract_docx(buf: io.BytesIO, name: str) -> StructuredDocument:
    document = Document(buf)
    blocks: list[ContentBlock] = []
    position = 0
    for item in _iter_block_items(document):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            heading_level = _heading_level(item)
            if heading_level is not None:
                blocks.append(
                    ContentBlock(
                        type="heading",
                        text=text,
                        level=heading_level,
                        metadata={
                            "position": position,
                            "style": item.style.name if item.style else None,
                        },
                    )
                )
            elif _paragraph_is_list(item):
                blocks.append(
                    ContentBlock(
                        type="list_item",
                        text=text,
                        level=_paragraph_list_level(item),
                        metadata={
                            "position": position,
                            "style": item.style.name if item.style else None,
                            "ordered": _paragraph_list_type(item) == "ordered",
                            "marker": (
                                "-"
                                if _paragraph_list_type(item) == "unordered"
                                else "1"
                            ),
                        },
                    )
                )
            else:
                blocks.append(
                    ContentBlock(
                        type="paragraph",
                        text=text,
                        metadata={
                            "position": position,
                            "style": item.style.name if item.style else None,
                        },
                    )
                )
        else:
            rows: list[list[str]] = []
            for row in item.rows:
                values = [cell.text.strip() for cell in row.cells]
                if any(values):
                    rows.append(values)
            if rows:
                block_text = "\n".join(" | ".join(row) for row in rows)
                blocks.append(
                    ContentBlock(
                        type="table",
                        text=block_text,
                        metadata={"position": position, "rows": rows},
                    )
                )
        position += 1
    return StructuredDocument.from_blocks(blocks, source=name)


def _extract_pdf(buf: io.BytesIO, name: str) -> StructuredDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(buf)
    except PdfReadError as exc:  # pragma: no cover - invalid PDFs
        raise ValueError("invalid pdf") from exc

    blocks: list[ContentBlock] = []
    for idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
            except ImportError as err:  # pragma: no cover - optional OCR
                raise RuntimeError("ocr dependencies missing") from err
            try:
                images = convert_from_bytes(
                    buf.getvalue(), fmt="png", first_page=idx, last_page=idx
                )
                ocr_text = "\n".join(pytesseract.image_to_string(img) for img in images)
                page_text = (page_text + "\n" + ocr_text).strip()
            except Exception as err:  # pragma: no cover - OCR failure
                raise RuntimeError("ocr failed") from err
        page_text = page_text.strip()
        if not page_text:
            continue
        segments = [
            seg.strip() for seg in re.split(r"\n{2,}", page_text) if seg.strip()
        ]
        if not segments:
            segments = [page_text]
        for pos, segment in enumerate(segments):
            blocks.append(
                ContentBlock(
                    type="paragraph",
                    text=segment,
                    metadata={"page": idx, "position": pos},
                )
            )
    return StructuredDocument.from_blocks(blocks, source=name)


def _parse_html_blocks(html: str) -> list[ContentBlock]:
    from bs4 import BeautifulSoup
    from bs4.element import Tag

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    body = soup.body or soup
    blocks: list[ContentBlock] = []
    position = 0
    for element in body.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"],
        recursive=True,
    ):
        if not isinstance(element, Tag):
            continue
        text = element.get_text(" ", strip=True)
        if not text or not element.name:
            continue
        if element.name.startswith("h"):
            try:
                level = int(element.name[1])
            except (ValueError, IndexError):  # pragma: no cover - defensive
                level = None
            blocks.append(
                ContentBlock(
                    type="heading",
                    text=text,
                    level=level,
                    metadata={"tag": element.name, "position": position},
                )
            )
        elif element.name == "li":
            ancestors = [
                ancestor
                for ancestor in element.parents
                if isinstance(ancestor, Tag) and ancestor.name in {"ul", "ol"}
            ]
            list_level = max(len(ancestors) - 1, 0)
            list_type = (
                "ordered" if ancestors and ancestors[0].name == "ol" else "unordered"
            )
            marker = "-" if list_type == "unordered" else str(position + 1)
            blocks.append(
                ContentBlock(
                    type="list_item",
                    text=text,
                    level=list_level,
                    metadata={
                        "position": position,
                        "list_type": list_type,
                        "ordered": list_type == "ordered",
                        "marker": marker,
                    },
                )
            )
        elif element.name == "table":
            rows: list[list[str]] = []
            for tr in element.find_all("tr"):
                if not isinstance(tr, Tag):
                    continue
                cells = [
                    cell.get_text(" ", strip=True)
                    for cell in tr.find_all(["td", "th"])
                    if isinstance(cell, Tag)
                ]
                if any(cells):
                    rows.append(cells)
            if rows:
                table_text = "\n".join(" | ".join(row) for row in rows)
                blocks.append(
                    ContentBlock(
                        type="table",
                        text=table_text,
                        metadata={"position": position, "rows": rows},
                    )
                )
        else:
            blocks.append(
                ContentBlock(
                    type="paragraph",
                    text=text,
                    metadata={"tag": element.name, "position": position},
                )
            )
        position += 1
    return blocks
