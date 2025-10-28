"""Utilities for detecting branding assets from company career pages."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_PILImage: Any
try:  # pragma: no cover - optional dependency guard
    from PIL import Image as _PILImage
except ImportError:  # pragma: no cover - optional dependency
    _PILImage = None

logger = logging.getLogger(__name__)

_LOGO_HINT_RE = re.compile(r"logo", re.IGNORECASE)
_META_LOGO_ATTRS: tuple[tuple[int, str, re.Pattern[str]], ...] = (
    (12, "property", re.compile(r"og:logo", re.IGNORECASE)),
    (11, "itemprop", re.compile(r"logo", re.IGNORECASE)),
    (10, "name", re.compile(r"og:logo", re.IGNORECASE)),
    (9, "property", re.compile(r"og:image", re.IGNORECASE)),
    (8, "name", re.compile(r"og:image", re.IGNORECASE)),
    (7, "name", re.compile(r"twitter:image", re.IGNORECASE)),
    (7, "property", re.compile(r"twitter:image", re.IGNORECASE)),
)
_TAGLINE_STOPWORDS = {
    "jobs",
    "stellen",
    "karriere",
    "career",
    "bewerb",
    "apply",
    "benefits",
    "aufgaben",
    "m/w/d",
    "mwd",
    "gn",
    "jobportal",
    "stellenangebot",
    "vakanz",
}

DEFAULT_BRAND_COLOR = "#2563EB"


@dataclass(slots=True)
class BrandAssets:
    """Container for detected branding information."""

    logo_url: str | None = None
    icon_url: str | None = None
    brand_color: str | None = None
    claim: str | None = None


def _clean_text(value: str | Sequence[Any] | None) -> str:
    if isinstance(value, str):
        candidate = value
    elif isinstance(value, Sequence):
        candidate = _pick_first_string(value) or ""
    else:
        candidate = ""
    cleaned = re.sub(r"\s+", " ", candidate).strip()
    return cleaned


def _pick_first_string(values: Sequence[Any]) -> str | None:
    for item in values:
        if isinstance(item, str) and item.strip():
            return item
    return None


def _resolve_url(base_url: str | None, asset_url: str | Sequence[Any] | None) -> str | None:
    if asset_url is None:
        return None
    if isinstance(asset_url, str):
        candidate = asset_url.strip()
    elif isinstance(asset_url, Sequence):
        candidate_value = _pick_first_string(asset_url)
        if not candidate_value:
            return None
        candidate = candidate_value.strip()
    else:
        return None
    if not candidate:
        return None
    if candidate.startswith("data:"):
        return None
    if base_url:
        return urljoin(base_url, candidate)
    return candidate


def _score_image(tag) -> int:
    score = 0
    alt = tag.get("alt") or ""
    src = tag.get("src") or ""
    tag_id = tag.get("id") or ""
    classes = " ".join(tag.get("class") or [])
    wrapper_classes = " ".join(tag.parent.get("class") or []) if tag.parent else ""
    text_blob = " ".join((alt, src, tag_id, classes, wrapper_classes))
    if _LOGO_HINT_RE.search(text_blob):
        score += 5
    width = tag.get("width") or tag.get("data-width")
    height = tag.get("height") or tag.get("data-height")
    try:
        if width and int(width) >= 120:
            score += 1
        if height and int(height) >= 120:
            score += 1
    except ValueError:
        pass
    if src.lower().endswith(".svg"):
        score += 1
    return score


def _select_logo_url(soup: BeautifulSoup, base_url: str | None) -> str | None:
    candidates: dict[str, int] = {}

    def _add_candidate(raw_url: str | Sequence[Any] | None, score: int) -> None:
        resolved = _resolve_url(base_url, raw_url)
        if not resolved:
            return
        existing = candidates.get(resolved)
        if existing is None or score > existing:
            candidates[resolved] = score

    for score, attr, pattern in _META_LOGO_ATTRS:
        for tag in soup.find_all("meta", attrs={attr: pattern}):
            content = tag.get("content")
            _add_candidate(content, score)

    for link in soup.find_all("link"):
        rel = link.get("rel")
        href = link.get("href")
        if not href or not rel:
            continue
        if isinstance(rel, Sequence) and not isinstance(rel, str):
            rel_tokens = " ".join(str(token) for token in rel)
        else:
            rel_tokens = str(rel)
        if _LOGO_HINT_RE.search(rel_tokens):
            _add_candidate(href, 11)

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        score = _score_image(img)
        if score:
            _add_candidate(src, score)

    if not candidates:
        return None

    return max(candidates.items(), key=lambda item: (item[1], item[0]))[0]


def _extract_icon_url(soup: BeautifulSoup, base_url: str | None) -> str | None:
    for rel in ("apple-touch-icon", "icon", "shortcut icon"):
        link = soup.find("link", rel=lambda value: value and rel in value.lower())
        if link and link.get("href"):
            resolved = _resolve_url(base_url, link.get("href"))
            if resolved:
                return resolved
    return None


def _download_image(url: str) -> bytes | None:
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "CognitiveStaffing/1.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        logger.debug("Failed to fetch branding image %s: %s", url, exc)
        return None
    return resp.content


def _dominant_color(image_bytes: bytes) -> str | None:
    if _PILImage is None:  # pragma: no cover - optional dependency missing
        return None
    try:
        with _PILImage.open(BytesIO(image_bytes)) as img:
            img = img.convert("RGBA")
            img = img.resize((64, 64))
            colors = img.getcolors(64 * 64)
    except Exception:  # pragma: no cover - defensive
        return None
    if not colors:
        return None
    filtered: list[tuple[int, tuple[int, int, int]]] = []
    for count, color in colors:
        r, g, b, a = color
        if a < 128:
            continue
        if r > 245 and g > 245 and b > 245:
            continue
        if r < 10 and g < 10 and b < 10:
            continue
        filtered.append((count, (r, g, b)))
    if not filtered:
        filtered = [(count, (r, g, b)) for count, (r, g, b, a) in colors if a >= 128]
    if not filtered:
        return None
    filtered.sort(key=lambda item: item[0], reverse=True)
    r, g, b = filtered[0][1]
    return f"#{r:02X}{g:02X}{b:02X}"


def _extract_theme_color(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": re.compile("theme-color", re.IGNORECASE)})
    if meta and meta.get("content"):
        candidate = _clean_text(meta.get("content"))
        if re.fullmatch(r"#?[0-9A-Fa-f]{6}", candidate):
            return candidate.upper() if candidate.startswith("#") else f"#{candidate.upper()}"
    return None


def _extract_claim(soup: BeautifulSoup) -> str | None:
    candidates: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "p"], limit=25):
        text = _clean_text(element.get_text(" "))
        if not text:
            continue
        lowered = text.lower()
        if any(stop in lowered for stop in _TAGLINE_STOPWORDS):
            continue
        if 8 <= len(text) <= 80:
            candidates.append(text)
    if not candidates:
        return None
    candidates.sort(key=lambda value: (-value.count("."), len(value)))
    return candidates[0]


def extract_brand_assets(html: str, *, base_url: str | None = None) -> BrandAssets:
    """Return detected branding assets from ``html``."""

    if not html or not html.strip():
        return BrandAssets()
    soup = BeautifulSoup(html, "html.parser")
    logo_url = _select_logo_url(soup, base_url)
    icon_url = _extract_icon_url(soup, base_url)
    theme_color = _extract_theme_color(soup)
    brand_color = theme_color

    if not brand_color and logo_url:
        image_bytes = _download_image(logo_url)
        if image_bytes:
            brand_color = _dominant_color(image_bytes)
    if not brand_color and icon_url:
        icon_bytes = _download_image(icon_url)
        if icon_bytes:
            brand_color = _dominant_color(icon_bytes)

    claim = _extract_claim(soup)

    return BrandAssets(
        logo_url=logo_url,
        icon_url=icon_url,
        brand_color=brand_color,
        claim=claim,
    )


def fetch_branding_assets(url: str, *, timeout: float = 8.0) -> BrandAssets:
    """Return branding assets for ``url`` with a safe default colour."""

    cleaned_url = (url or "").strip()
    if not cleaned_url:
        return BrandAssets(brand_color=DEFAULT_BRAND_COLOR)

    try:
        response = requests.get(
            cleaned_url,
            timeout=timeout,
            headers={"User-Agent": "CognitiveStaffing/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        logger.debug("Failed to download branding source %s: %s", cleaned_url, exc)
        return BrandAssets(brand_color=DEFAULT_BRAND_COLOR)

    html = response.text or ""
    base_url = response.url or cleaned_url

    try:
        assets = extract_brand_assets(html, base_url=base_url)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug("Brand asset extraction crashed for %s: %s", cleaned_url, exc)
        return BrandAssets(brand_color=DEFAULT_BRAND_COLOR)

    if not assets.brand_color:
        assets.brand_color = DEFAULT_BRAND_COLOR

    return assets


__all__ = ["DEFAULT_BRAND_COLOR", "BrandAssets", "extract_brand_assets", "fetch_branding_assets"]
