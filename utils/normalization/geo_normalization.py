"""Geographic normalisation helpers and pycountry lookups."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from importlib import import_module
from types import ModuleType
from typing import Iterable, List, Optional

import config as app_config
from config import is_llm_enabled
from config.models import ModelTask, get_model_for
from llm.openai_responses import build_json_schema_format, call_responses_safe

logger = logging.getLogger("cognitive_needs.normalization")

pycountry: ModuleType | None
try:  # pragma: no cover - optional dependency guard
    pycountry = import_module("pycountry")
except ImportError:  # pragma: no cover - fallback when dependency missing
    pycountry = None

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
    "dänisch": "Danish",
    "dan": "Danish",
    "danish": "Danish",
    "da": "Danish",
    "englisch": "English",
    "en": "English",
    "eng": "English",
    "english": "English",
    "es": "Spanish",
    "esp": "Spanish",
    "spa": "Spanish",
    "spanisch": "Spanish",
    "spanish": "Spanish",
    "finnish": "Finnish",
    "finnisch": "Finnish",
    "fin": "Finnish",
    "fi": "Finnish",
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "französisch": "French",
    "french": "French",
    "hindi": "Hindi",
    "italian": "Italian",
    "italienisch": "Italian",
    "ita": "Italian",
    "it": "Italian",
    "mandarin": "Chinese",
    "mandarin chinese": "Chinese",
    "niederländisch": "Dutch",
    "nl": "Dutch",
    "nld": "Dutch",
    "dut": "Dutch",
    "holländisch": "Dutch",
    "dutch": "Dutch",
    "nor": "Norwegian",
    "no": "Norwegian",
    "norwegian": "Norwegian",
    "norwegisch": "Norwegian",
    "polish": "Polish",
    "polnisch": "Polish",
    "pl": "Polish",
    "pol": "Polish",
    "portuguesisch": "Portuguese",
    "portuguese": "Portuguese",
    "português": "Portuguese",
    "por": "Portuguese",
    "pt": "Portuguese",
    "russian": "Russian",
    "russisch": "Russian",
    "rus": "Russian",
    "ru": "Russian",
    "schwedisch": "Swedish",
    "swedish": "Swedish",
    "swe": "Swedish",
    "sv": "Swedish",
    "tschechisch": "Czech",
    "czech": "Czech",
    "ces": "Czech",
    "cs": "Czech",
    "turkish": "Turkish",
    "türkisch": "Turkish",
    "tur": "Turkish",
    "tr": "Turkish",
    "arabic": "Arabic",
    "arabisch": "Arabic",
    "ara": "Arabic",
    "ar": "Arabic",
    "chinesisch": "Chinese",
    "chinese": "Chinese",
    "chi": "Chinese",
    "zho": "Chinese",
    "zh": "Chinese",
    "中文": "Chinese",
}

_CITY_LEADING_PATTERN = re.compile(
    r"^(?:in|im|in\s+der|in\s+den|in\s+dem|in\s+die|in\s+das|bei|beim|am|an|auf|aus|vom|von|von\s+der|von\s+den|nahe|nahe\s+bei|nahe\s+von|nähe\s+von|rund\s+um)\s+",
    re.IGNORECASE,
)

_CITY_EXTRACTION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "Primary city name without prefixes, suffixes, or country information.",
        }
    },
    "required": ["city"],
}

_CITY_EXTRACTION_SYSTEM_PROMPT = (
    "Extract the primary city mentioned in the given text. Respond strictly with JSON "
    "containing a single 'city' field. Use an empty string when no city is present."
)

_CITY_TOKEN_STRIP_RE = re.compile(r"^[\s,.;:()\[\]\-]+|[\s,.;:()\[\]\-]+$")


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


def _normalize_city_with_regex(value: Optional[str]) -> str:
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


def _llm_extract_city(value: str) -> str:
    """Return a city extracted from ``value`` using the Responses API fallback."""

    if not app_config.USE_RESPONSES_API or not is_llm_enabled():
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    response_format = build_json_schema_format(
        name="extract_city",
        schema=_CITY_EXTRACTION_SCHEMA,
        strict=True,
    )
    messages = [
        {"role": "system", "content": _CITY_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": cleaned},
    ]
    try:
        result = call_responses_safe(
            messages,
            model=get_model_for(ModelTask.EXTRACTION),
            response_format=response_format,
            temperature=0,
            max_completion_tokens=40,
            reasoning_effort="minimal",
            task=ModelTask.EXTRACTION,
            logger_instance=logger,
            context="city extraction",
        )
    except Exception:
        logger.debug("City extraction fallback failed", exc_info=True)
        return ""

    if result is None:
        logger.info("City extraction fell back to heuristics after Responses/Chat failure")
        return ""

    if result.used_chat_fallback:
        logger.info("City extraction used classic chat fallback")
    content = (result.content or "").strip()
    if not content:
        return ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.debug("City extraction fallback returned non-JSON payload: %s", content)
        return ""
    city_value = payload.get("city")
    if not isinstance(city_value, str):
        return ""
    normalized = _normalize_city_with_regex(city_value)
    return normalized or city_value.strip()


def normalize_city_name(value: Optional[str]) -> str:
    """Return ``value`` as a cleaned city name with an LLM fallback when needed."""

    normalized = _normalize_city_with_regex(value)
    if normalized:
        return normalized
    original = value.strip() if isinstance(value, str) else ""
    if not original:
        return ""
    fallback = _llm_extract_city(original)
    if fallback:
        return fallback
    return ""


__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
    "normalize_city_name",
]
