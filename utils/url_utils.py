"""Utilities for extracting text from web pages."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup


def extract_text_from_url(url: str) -> str:
    """Fetch and clean textual content from a URL.

    Args:
        url: Target web page URL.

    Returns:
        The extracted plain text.

    Raises:
        ValueError: If the URL cannot be retrieved.
    """

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {url}") from exc
    soup = BeautifulSoup(response.text, "html.parser")
    for sel in ["article", "main"]:
        node = soup.select_one(sel)
        if node:
            return " ".join(node.get_text(separator=" ").split())
    return " ".join(soup.get_text(separator=" ").split())
