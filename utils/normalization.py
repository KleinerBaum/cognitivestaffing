"""Utilities for normalising geographic, language and profile inputs."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any, Callable, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

from pydantic import ValidationError

from config import ModelTask, USE_RESPONSES_API, get_model_for, is_llm_enabled
from llm.openai_responses import build_json_schema_format, call_responses
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
_PHONE_GROUP_RE = re.compile(r"\+?\d+")
_PHONE_EXTENSION_RE = re.compile(r"(?:ext\.?|x)\s*(\d+)$", re.IGNORECASE)
_URL_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


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
        head = groups[0].lstrip("+")
        if head:
            result_parts.append(head)
        tail = "".join(part.lstrip("+") for part in groups[1:])
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

_COMPANY_SIZE_NUMBER_RE = re.compile(r"\d+(?:[.\s,]\d{3})*(?:[.,]\d+)?")
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

_COMPANY_SIZE_SNIPPET_RE = re.compile(
    r"""
    (?P<prefix>\b(?:über|ueber|mehr\s+als|mindestens|at\s+least|ab|around|approx(?:\.?)|approximately|rund|circa|ca\.?,?|etwa|ungefähr|ungefaehr|knapp|more\s+than)\s+)?
    (?P<first>\d{1,3}(?:[.\s,]\d{3})*(?:[.,]\d+)?)
    (?P<range>
        \s*(?:[-–—]\s*|bis\s+|to\s+)
        (?P<second>\d{1,3}(?:[.\s,]\d{3})*(?:[.,]\d+)?)
    )?
    (?P<suffix>\s*\+)?\s*
    (?P<unit>Mitarbeiter(?::innen)?|Mitarbeiterinnen|Mitarbeitende|Beschäftigte[n]?|Angestellte|Menschen|people|employees|staff)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_COMPANY_SIZE_THOUSAND_SEP_RE = re.compile(r"(?<=\d)[.,](?=\d{3}(?:\D|$))")


def _normalize_company_size_input(value: str) -> str:
    """Return ``value`` with normalised spacing for consistent parsing."""

    replacements = {
        "\u202f": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u2007": " ",
        "\u00a0": " ",
    }
    candidate = value
    for original, replacement in replacements.items():
        candidate = candidate.replace(original, replacement)
    return candidate


def _coerce_company_size_token(token: str) -> int | None:
    """Convert ``token`` into an integer employee count when possible."""

    cleaned = token.strip()
    if not cleaned:
        return None
    cleaned = _normalize_company_size_input(cleaned)
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace("'", "").replace("’", "")
    cleaned = _COMPANY_SIZE_THOUSAND_SEP_RE.sub("", cleaned)
    integer_part = re.split(r"[.,]", cleaned)[0]
    if not integer_part:
        return None
    try:
        return int(integer_part)
    except ValueError:
        return None


def extract_company_size_snippet(value: str | None) -> str:
    """Return the matching size snippet from ``value`` if present."""

    if not value:
        return ""
    candidate = _normalize_company_size_input(value)
    match = _COMPANY_SIZE_SNIPPET_RE.search(candidate)
    if not match:
        return ""
    snippet = match.group(0)
    snippet = " ".join(snippet.strip().split())
    return snippet


def extract_company_size(value: str | None) -> str:
    """Return a normalised employee count extracted from ``value``."""

    snippet = extract_company_size_snippet(value)
    if not snippet:
        return ""
    normalised = normalize_company_size(snippet)
    return normalised


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


def _llm_extract_city(value: str) -> str:
    """Return a city extracted from ``value`` using the Responses API fallback."""

    if not USE_RESPONSES_API or not is_llm_enabled():
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
        result = call_responses(
            messages,
            model=get_model_for(ModelTask.EXTRACTION),
            response_format=response_format,
            temperature=0,
            max_tokens=40,
            reasoning_effort="minimal",
            task=ModelTask.EXTRACTION,
        )
    except Exception:
        logger.debug("City extraction fallback failed", exc_info=True)
        return ""
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


def _parse_company_numbers(value: str) -> list[int]:
    numbers: list[int] = []
    candidate = _normalize_company_size_input(value)
    for match in _COMPANY_SIZE_NUMBER_RE.finditer(candidate):
        token = match.group(0)
        coerced = _coerce_company_size_token(token)
        if coerced is not None:
            numbers.append(coerced)
    return numbers


def normalize_company_size(value: Optional[str]) -> str:
    """Return a clean numeric representation for ``value`` when possible."""

    if value is None:
        return ""
    candidate = _normalize_company_size_input(value)
    candidate = " ".join(candidate.strip().split())
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


def _validate_profile_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, ValidationError | None]:
    """Validate ``payload`` against :class:`NeedAnalysisProfile`."""

    from models.need_analysis import NeedAnalysisProfile as _Profile

    try:
        model = _Profile.model_validate(payload)
    except ValidationError as exc:
        return None, exc
    return model.model_dump(), None


def _attempt_llm_repair(
    payload: Mapping[str, Any],
    *,
    errors: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    """Try to repair ``payload`` via the JSON repair fallback."""

    try:
        from llm.json_repair import repair_profile_payload
    except Exception:  # pragma: no cover - defensive fallback when imports fail
        logger.exception("Unable to import JSON repair helper")
        return None

    repaired = repair_profile_payload(payload, errors=errors)
    if not repaired:
        return None
    if not isinstance(repaired, Mapping):
        return None
    normalized_repair = _normalize_profile_mapping(repaired)
    return normalized_repair


def normalize_profile(profile: Mapping[str, Any] | "NeedAnalysisProfile") -> dict[str, Any]:
    """Return a validated, cleaned dictionary representation of ``profile``.

    The helper cleans scalar strings, deduplicates list entries, harmonises
    known fields (job title, city, country, branding metadata) and re-validates
    the resulting payload. If normalisation yields an invalid payload, it uses
    the OpenAI JSON repair fallback to recover when available.
    """

    is_model_input = hasattr(profile, "model_dump")
    if is_model_input:
        data = profile.model_dump()  # type: ignore[assignment]
    elif isinstance(profile, Mapping):
        data = dict(profile)
    else:  # pragma: no cover - defensive branch
        raise TypeError("profile must be a mapping or NeedAnalysisProfile instance")

    normalized = _normalize_profile_mapping(data)

    if is_model_input and normalized == data:
        return dict(normalized)

    validated, error = _validate_profile_payload(normalized)
    if validated is not None:
        return validated

    errors = error.errors() if error else None
    repaired_payload = _attempt_llm_repair(normalized, errors=errors)
    if repaired_payload is not None:
        repaired_validated, repair_error = _validate_profile_payload(repaired_payload)
        if repaired_validated is not None:
            logger.info("Normalized profile repaired via JSON fallback.")
            return repaired_validated
        logger.warning(
            "JSON repair fallback returned invalid payload: %s",
            repair_error,
        )

    if is_model_input:
        logger.warning(
            "Normalization produced invalid payload; returning original model dump.",
        )
        return dict(data)

    logger.warning(
        "Normalization could not validate payload; returning NeedAnalysisProfile defaults.",
    )
    default_model, _ = _validate_profile_payload({})
    return default_model if default_model is not None else {}


__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
    "normalize_city_name",
    "normalize_company_size",
    "normalize_profile",
    "extract_company_size",
    "extract_company_size_snippet",
]
