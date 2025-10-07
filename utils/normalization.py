"""Utilities for normalising country and language inputs."""

from __future__ import annotations

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


__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
]
