"""Utilities for normalising geographic, language and profile inputs."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any, Callable, List, Optional, Sequence, TYPE_CHECKING

from utils.patterns import GENDER_SUFFIX_INLINE_RE, GENDER_SUFFIX_TRAILING_RE

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from models.need_analysis import NeedAnalysisProfile

try:  # pragma: no cover - optional dependency guard
    import pycountry
except ImportError:  # pragma: no cover - fallback when dependency missing
    pycountry = None


logger = logging.getLogger("cognitive_needs.normalization")
HEURISTICS_LOGGER = logging.getLogger("cognitive_needs.heuristics")

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_SEPARATORS_RE = re.compile(r"[\s\-\u2013\u2014|/:,;]+$")
_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_STRIP_CHARACTERS = "\u200b\u200c\u200d\ufeff\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"  # control chars
_QUOTE_CHARACTERS = "\"'`´“”„‚‘’«»‹›"


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

_COMPANY_SIZE_NUMBER_RE = re.compile(r"\d+(?:[.\s]\d{3})*(?:,\d+)?")
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


def _clean_string(value: str) -> str:
    """Return ``value`` normalised for whitespace and stripped of wrappers."""

    candidate = value.replace("\xa0", " ")
    candidate = candidate.replace("\u2009", " ")
    candidate = candidate.translate({ord(ch): None for ch in _STRIP_CHARACTERS})
    candidate = _WHITESPACE_RE.sub(" ", candidate)
    candidate = candidate.strip()
    candidate = candidate.strip(_QUOTE_CHARACTERS)
    return candidate.strip()


def _normalize_job_title_value(value: str) -> str:
    """Normalise job titles by trimming gender markers and separators."""

    cleaned = GENDER_SUFFIX_INLINE_RE.sub("", value)
    cleaned = GENDER_SUFFIX_TRAILING_RE.sub("", cleaned)
    cleaned = _TRAILING_SEPARATORS_RE.sub("", cleaned)
    return cleaned.strip()


def _normalize_city_value(value: str) -> str:
    """Return ``value`` cleaned as a city name using domain heuristics."""

    normalised = normalize_city_name(value)
    return normalised


def _normalize_country_value(value: str) -> str:
    """Normalise ``value`` to a canonical country representation."""

    country = normalize_country(value)
    return country or value


def _normalize_brand_color_value(value: str) -> str:
    """Return a normalised hex colour when possible."""

    if not value:
        return ""
    candidate = value.upper()
    if _HEX_COLOR_RE.match(candidate):
        hex_value = candidate.lstrip("#")
        return f"#{hex_value}"
    return candidate


def _normalize_logo_url(value: str) -> str:
    """Trim surrounding whitespace without altering URL structure."""

    return value.strip()


def _normalize_string_list_field(values: Sequence[Any]) -> list[str]:
    """Clean string lists by trimming items, removing empties and duplicates."""

    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        cleaned = _clean_string(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _truncate_value(value: Any, limit: int = 160) -> str:
    """Return ``value`` as a shortened string for logging purposes."""

    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _log_change(path: str, before: Any, after: Any, rule: str) -> None:
    """Emit a heuristic log entry describing a normalisation change."""

    HEURISTICS_LOGGER.info(
        "Normalized %s via %s",
        path,
        rule,
        extra={
            "heuristic_field": path,
            "heuristic_rule": f"normalize.{rule}",
            "normalizer_before": _truncate_value(before),
            "normalizer_after": _truncate_value(after),
        },
    )


_STRING_RULES: dict[str, tuple[str, Callable[[str], str]]] = {
    "company.brand_color": ("brand.color", _normalize_brand_color_value),
    "company.logo_url": ("brand.logo_url", _normalize_logo_url),
    "position.job_title": ("job_title.strip_gender", _normalize_job_title_value),
    "location.primary_city": ("location.city", _normalize_city_value),
    "location.country": ("location.country", _normalize_country_value),
}


_STRING_LIST_FIELDS = {
    "responsibilities.items",
    "requirements.hard_skills_required",
    "requirements.hard_skills_optional",
    "requirements.soft_skills_required",
    "requirements.soft_skills_optional",
    "requirements.tools_and_technologies",
    "requirements.languages_required",
    "requirements.languages_optional",
    "requirements.certificates",
    "requirements.certifications",
    "employment.travel_regions",
    "employment.travel_continents",
    "compensation.benefits",
}


def _normalize_value(value: Any, path: str) -> Any:
    base_path = path.split("[")[0]
    if isinstance(value, Mapping):
        normalized = {key: _normalize_value(val, f"{path}.{key}" if path else key) for key, val in value.items()}
        return normalized
    if isinstance(value, list):
        return _normalize_list(value, base_path)
    if isinstance(value, str):
        cleaned = _clean_string(value)
        rule_name = "string.clean"
        rule = _STRING_RULES.get(base_path)
        if rule is not None:
            rule_name, func = rule
            special = func(cleaned)
            cleaned = special
        if not cleaned:
            cleaned_value: Any = None
        else:
            cleaned_value = cleaned
        if cleaned_value != value:
            _log_change(base_path, value, cleaned_value, rule_name)
        return cleaned_value
    return value


def _normalize_list(values: Sequence[Any], path: str) -> list[Any]:
    if path in _STRING_LIST_FIELDS:
        original = list(values)
        normalized = _normalize_string_list_field(original)
        if normalized != original:
            _log_change(path, original, normalized, "list.clean")
        return normalized
    normalized_list: list[Any] = []
    for index, item in enumerate(values):
        normalized_list.append(_normalize_value(item, f"{path}[{index}]"))
    return normalized_list


def _normalize_profile_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {key: _normalize_value(value, key) for key, value in data.items()}
    return normalized


def normalize_profile(profile: "NeedAnalysisProfile") -> "NeedAnalysisProfile":
    """Return a normalised copy of ``profile`` with cleaned scalar fields."""

    try:
        data = profile.model_dump()
    except AttributeError:
        return profile
    normalized = _normalize_profile_mapping(data)
    if normalized == data:
        return profile
    try:
        from models.need_analysis import NeedAnalysisProfile as _Profile

        return _Profile.model_validate(normalized)
    except Exception:  # pragma: no cover - defensive fallback
        logger.exception("Failed to validate normalized profile; returning original")
        return profile


__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
    "normalize_city_name",
    "normalize_company_size",
    "normalize_profile",
]
