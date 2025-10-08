"""Utilities for extracting text from web pages."""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "CognitiveNeeds/1.0"}


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
    soup = BeautifulSoup(response.text, "html.parser")
    for sel in ["article", "main"]:
        node = soup.select_one(sel)
        if node:
            return " ".join(node.get_text(separator=" ").split())
    return " ".join(soup.get_text(separator=" ").split())
