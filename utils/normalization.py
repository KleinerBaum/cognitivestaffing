"""Utilities for normalising geographic and language inputs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from typing import List, Optional

try:  # pragma: no cover - optional dependency guard
    import pycountry
except ImportError:  # pragma: no cover - fallback when dependency missing
    pycountry = None  # type: ignore[assignment]


_COUNTRY_OVERRIDES: dict[str, str] = {
    "bundesrepublik deutschland": "Germany",
    "de": "Germany",
    "deu": "Germany",
    "deutschland": "Germany",
    "germany": "Germany",
    "österreich": "Austria",
    "oesterreich": "Austria",
    "schweiz": "Switzerland",
    "ch": "Switzerland",
    "che": "Switzerland",
}

_COUNTRY_CODE_OVERRIDES: dict[str, str] = {
    "germany": "DE",
    "austria": "AT",
    "switzerland": "CH",
}

_LANGUAGE_OVERRIDES: dict[str, str] = {
    "de": "German",
    "deu": "German",
    "ger": "German",
    "german": "German",
    "deutsch": "German",
    "englisch": "English",
    "en": "English",
    "eng": "English",
    "english": "English",
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "französisch": "French",
    "french": "French",
    "es": "Spanish",
    "esp": "Spanish",
    "spa": "Spanish",
    "spanisch": "Spanish",
    "spanish": "Spanish",
}


def _candidate_country_name(record: object) -> Optional[str]:
    for attr in ("common_name", "name", "official_name"):
        name = getattr(record, attr, None)
        if isinstance(name, str) and name.strip():
            return name
    return None


@lru_cache(maxsize=1024)
def _lookup_country(value: str) -> Optional[str]:
    if pycountry is None:
        return None
    try:
        record = pycountry.countries.lookup(value)
    except LookupError:
        return None
    name = _candidate_country_name(record)
    return name


@lru_cache(maxsize=2048)
def _lookup_language(value: str) -> Optional[str]:
    if pycountry is None:
        return None
    try:
        record = pycountry.languages.lookup(value)
    except LookupError:
        return None
    for attr in ("name", "common_name"):
        name = getattr(record, attr, None)
        if isinstance(name, str) and name.strip():
            return name
    return None


def normalize_country(value: Optional[str]) -> Optional[str]:
    """Normalise ``value`` to an English country name if possible."""

    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    country = _lookup_country(cleaned)
    if not country:
        override = _COUNTRY_OVERRIDES.get(cleaned.casefold())
        if override:
            country = override
    if not country:
        # Preserve short codes in uppercase and title-case longer names
        if cleaned.isupper() and len(cleaned) <= 3:
            return cleaned.upper()
        return cleaned.title() if len(cleaned) > 1 else cleaned
    return country


@lru_cache(maxsize=1024)
def country_to_iso2(value: Optional[str]) -> Optional[str]:
    """Return the ISO 3166-1 alpha-2 code for ``value`` if determinable."""

    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned.upper()

    override = _COUNTRY_CODE_OVERRIDES.get(cleaned.casefold())
    if override:
        return override

    if pycountry is not None:
        try:
            record = pycountry.countries.lookup(cleaned)
        except LookupError:
            record = None
        if record is not None:
            alpha_2 = getattr(record, "alpha_2", None)
            if isinstance(alpha_2, str) and alpha_2.strip():
                return alpha_2.upper()

    normalized = normalize_country(cleaned)
    if normalized:
        override = _COUNTRY_CODE_OVERRIDES.get(normalized.casefold())
        if override:
            return override
        if pycountry is not None:
            try:
                record = pycountry.countries.lookup(normalized)
            except LookupError:
                record = None
            if record is not None:
                alpha_2 = getattr(record, "alpha_2", None)
                if isinstance(alpha_2, str) and alpha_2.strip():
                    return alpha_2.upper()
    return None


def normalize_language(value: Optional[str]) -> Optional[str]:
    """Normalise ``value`` to an English language name if possible."""

    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    override = _LANGUAGE_OVERRIDES.get(cleaned.casefold())
    if override:
        return override
    language = _lookup_language(cleaned)
    if language:
        canonical = _LANGUAGE_OVERRIDES.get(language.casefold())
        return canonical or language
    if cleaned.isupper() and len(cleaned) <= 3:
        return cleaned.upper()
    return cleaned.title() if len(cleaned) > 1 else cleaned


def normalize_language_list(values: Iterable[str] | None) -> List[str]:
    """Normalise and deduplicate ``values`` preserving order."""

    if not values:
        return []
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        normalized = normalize_language(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


_CITY_LEADING_PATTERN = re.compile(
    r"^(?:in|im|in\s+der|in\s+den|in\s+dem|in\s+die|in\s+das|bei|beim|am|an|auf|aus|vom|von|von\s+der|von\s+den|nahe|nahe\s+bei|nahe\s+von|nähe\s+von|rund\s+um)\s+",
    re.IGNORECASE,
)

_CITY_TOKEN_STRIP_RE = re.compile(r"^[\s,.;:()\[\]\-]+|[\s,.;:()\[\]\-]+$")

_COMPANY_SIZE_NUMBER_RE = re.compile(r"\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+")
_COMPANY_SIZE_PLUS_MARKERS = (
    "über",
    "mehr als",
    "more than",
    "mindestens",
    "at least",
    "ab",
    "plus",
    "+",
)


def _normalize_city_tokens(tokens: list[str]) -> list[str]:
    """Return ``tokens`` without trailing lowercase fragments."""

    while tokens:
        candidate = tokens[-1]
        cleaned = _CITY_TOKEN_STRIP_RE.sub("", candidate)
        if not cleaned:
            tokens.pop()
            continue
        if any(char.isdigit() for char in cleaned):
            break
        if cleaned[0].isupper() or any(char.isupper() for char in cleaned[1:]):
            break
        tokens.pop()
    return tokens


def normalize_city_name(value: Optional[str]) -> str:
    """Return ``value`` cleaned from leading articles and trailing fragments."""

    if value is None:
        return ""
    candidate = " ".join(value.strip().split())
    if not candidate:
        return ""
    candidate = _CITY_LEADING_PATTERN.sub("", candidate).strip()
    if not candidate:
        return ""
    for splitter in ("|", "/"):
        if splitter in candidate:
            candidate = candidate.split(splitter, 1)[0].strip()
    if "," in candidate:
        head, tail = candidate.split(",", 1)
        # Only keep the head when the tail starts lowercase (likely continuation).
        if tail and tail.lstrip() and tail.lstrip()[0].islower():
            candidate = head.strip()
    tokens = candidate.split()
    if not tokens:
        return ""
    tokens = _normalize_city_tokens(tokens)
    normalized = " ".join(tokens).strip(" ,.;:|-/")
    if not normalized or not any(ch.isalpha() for ch in normalized):
        return ""
    return normalized


def _parse_company_numbers(value: str) -> list[int]:
    numbers: list[int] = []
    for match in _COMPANY_SIZE_NUMBER_RE.finditer(value):
        token = match.group(0)
        token = token.replace(".", "").replace(" ", "")
        if "," in token:
            token = token.split(",", 1)[0]
        try:
            numbers.append(int(token))
        except ValueError:
            continue
    return numbers


def normalize_company_size(value: Optional[str]) -> str:
    """Return a clean numeric representation for ``value`` when possible."""

    if value is None:
        return ""
    candidate = " ".join(value.strip().split())
    if not candidate:
        return ""
    lowered = candidate.casefold()
    plus = any(marker in lowered for marker in _COMPANY_SIZE_PLUS_MARKERS)
    numbers = _parse_company_numbers(candidate)
    if not numbers:
        return ""
    if len(numbers) >= 2 and numbers[1] >= numbers[0]:
        return f"{numbers[0]}-{numbers[1]}"
    suffix = "+" if plus else ""
    return f"{numbers[0]}{suffix}"


__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
    "normalize_city_name",
    "normalize_company_size",
]
