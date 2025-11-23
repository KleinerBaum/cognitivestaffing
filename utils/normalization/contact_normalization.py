"""Contact detail normalization helpers."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

_STRIP_CHARACTERS = "\u200b\u200c\u200d\ufeff\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"  # control chars
_QUOTE_CHARACTERS = "\"'`´“”„‚‘’«»‹›"
_PHONE_GROUP_RE = re.compile(r"\+?\d+")
_PHONE_EXTENSION_RE = re.compile(r"(?:ext\.?|x)\s*(\d+)$", re.IGNORECASE)
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def normalize_phone_number(value: Optional[str]) -> Optional[str]:
    """Return a cleaned representation of ``value`` if it resembles a phone."""

    if value is None:
        return None
    candidate = value if isinstance(value, str) else str(value)
    stripped = candidate.strip()
    if not stripped:
        return None
    stripped = stripped.strip(_STRIP_CHARACTERS + _QUOTE_CHARACTERS)
    if not stripped:
        return None

    extension = None
    ext_match = _PHONE_EXTENSION_RE.search(stripped)
    if ext_match:
        extension = ext_match.group(1)
        stripped = stripped[: ext_match.start()]

    stripped = stripped.replace("\u00a0", " ")
    stripped = re.sub(r"\(0\)", " ", stripped)
    stripped = re.sub(r"[()\[\]{}]", " ", stripped)
    stripped = re.sub(r"[./\\-]", " ", stripped)
    stripped = re.sub(r"[,;]+", " ", stripped)
    stripped = stripped.rstrip(" .-;")
    stripped = re.sub(r"\s+", " ", stripped)
    if stripped.startswith("+ "):
        stripped = "+" + stripped[2:]

    groups = _PHONE_GROUP_RE.findall(stripped)
    if not groups:
        return None

    digit_count = sum(len(group.lstrip("+")) for group in groups)
    if digit_count < 3:
        return None

    result_parts: list[str] = []
    if groups[0].startswith("+"):
        country_digits = groups[0][1:]
        if country_digits:
            result_parts.append(f"+{country_digits}")
        else:
            result_parts.append("+")
        remaining = [part.lstrip("+") for part in groups[1:]]
        if remaining:
            area = remaining[0]
            if area:
                result_parts.append(area)
            tail = "".join(remaining[1:])
            if tail:
                result_parts.append(tail)
    else:
        head = groups[0]
        result_parts.append(head)
        tail = "".join(groups[1:])
        if tail:
            result_parts.append(tail)

    result = " ".join(part for part in result_parts if part)
    if not result:
        return None
    if extension:
        result = f"{result} ext {extension}"
    return result


def normalize_website_url(value: Optional[str]) -> Optional[str]:
    """Return ``value`` normalised to a canonical HTTPS URL when possible."""

    if value is None:
        return None
    candidate = value if isinstance(value, str) else str(value)
    stripped = candidate.strip()
    if not stripped:
        return None
    stripped = stripped.strip(_STRIP_CHARACTERS + _QUOTE_CHARACTERS)
    stripped = stripped.rstrip(".,; ")
    if not stripped:
        return None
    stripped = re.sub(r"\s+", "", stripped)

    if not _URL_SCHEME_RE.match(stripped):
        stripped = f"https://{stripped}"

    parsed = urlparse(stripped, scheme="https")
    netloc = parsed.netloc or ""
    path = parsed.path or ""
    if not netloc and path:
        netloc, path = path, ""
    netloc = netloc.strip()
    if not netloc:
        return None
    netloc = netloc.lower()
    path = re.sub(r"/{2,}", "/", path)
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    query = parsed.query
    fragment = parsed.fragment
    normalized = urlunparse((scheme, netloc, path, "", query, fragment))
    if not path and not query and not fragment and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


__all__ = ["normalize_phone_number", "normalize_website_url"]
