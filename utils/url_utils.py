"""Utilities for extracting text from web pages."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup


def extract_text_from_url(url: str) -> str:
    """Retrieve and clean textual content from a web page.

    Args:
        url: The target page URL.

    Returns:
        The cleaned text content or an empty string if fetching fails.
    """

    try:
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return ""
        from readability import Document

        doc = Document(response.text)
        soup = BeautifulSoup(doc.summary(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return ""
