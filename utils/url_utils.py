"""Utilities for extracting text from web pages."""

from __future__ import annotations

from html.parser import HTMLParser
import importlib.util
import logging
from typing import Any, Iterable
from urllib.parse import urlparse

import requests

_BS4_SPEC = importlib.util.find_spec("bs4")
BeautifulSoup: Any | None
if _BS4_SPEC is not None:  # pragma: no branch - deterministic branch
    from bs4 import BeautifulSoup as _BeautifulSoup

    BeautifulSoup = _BeautifulSoup
else:  # pragma: no cover - executed only when dependency missing
    BeautifulSoup = None

_LOGGER = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "CognitiveNeeds/1.0"}
_BLOCK_ELEMENTS: frozenset[str] = frozenset(
    {
        "article",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "section",
    }
)
_SKIP_ELEMENTS: frozenset[str] = frozenset({"script", "style"})


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML to text converter used when BeautifulSoup is unavailable."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Iterable[tuple[str, str | None]] | list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_ELEMENTS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and tag in _BLOCK_ELEMENTS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_ELEMENTS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and tag in _BLOCK_ELEMENTS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def get_text(self) -> str:
        return _normalize_whitespace("".join(self._parts))


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _extract_with_bs4(html: str) -> str:
    if BeautifulSoup is None:  # pragma: no cover - guarded by import detection
        raise RuntimeError("BeautifulSoup is not available")
    soup = BeautifulSoup(html, "html.parser")
    for selector in ("article", "main"):
        node = soup.select_one(selector)
        if node:
            return _normalize_whitespace(node.get_text(separator=" "))
    return _normalize_whitespace(soup.get_text(separator=" "))


def _extract_with_fallback(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def is_supported_url(url: str) -> bool:
    """Return ``True`` if ``url`` uses HTTP(S) and contains a host component."""

    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(parsed.netloc)


def extract_text_from_url(url: str) -> str:
    """Fetch and clean textual content from a URL.

    Args:
        url: Target web page URL.

    Returns:
        The extracted plain text.

    Raises:
        ValueError: If the URL is invalid or cannot be retrieved.
    """

    url = url.strip()
    if not is_supported_url(url):
        raise ValueError("Invalid URL")

    try:
        response = requests.get(url, timeout=15, headers=_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        raise ValueError(f"Failed to fetch URL: {url}") from exc

    html = response.text
    if BeautifulSoup is not None:
        return _extract_with_bs4(html)

    _LOGGER.warning("BeautifulSoup dependency missing – falling back to simplified HTML parsing")
    return _extract_with_fallback(html)
