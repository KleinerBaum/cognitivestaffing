"""Profile-wide normalization utilities and heuristics."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, cast

from pydantic import ValidationError

from core.schema_registry import load_need_analysis_schema
from llm.profile_normalization import normalize_interview_stages_field
from utils.normalization_payloads import NormalizedProfilePayload
from utils.patterns import GENDER_SUFFIX_INLINE_RE, GENDER_SUFFIX_TRAILING_RE
from utils.skill_taxonomy import build_skill_mappings

from .geo_normalization import normalize_city_name, normalize_country

if TYPE_CHECKING:
    from models.need_analysis import NeedAnalysisProfile

logger = logging.getLogger("cognitive_needs.normalization")
HEURISTICS_LOGGER = logging.getLogger("cognitive_needs.heuristics")
_MISSING = object()

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_SEPARATORS_RE = re.compile(r"[\s\-\u2013\u2014|/:,;]+$")
_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
_STRIP_CHARACTERS = "\u200b\u200c\u200d\ufeff\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"  # control chars
_QUOTE_CHARACTERS = "\"'`´“”„‚‘’«»‹›"

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


@lru_cache(maxsize=1)
def _load_need_analysis_schema() -> dict[str, Any]:
    """Return the NeedAnalysis JSON schema from the central registry."""

    return load_need_analysis_schema()


def _extract_type_set(schema: Mapping[str, Any]) -> set[str]:
    """Return a normalised set of ``type`` markers from ``schema``."""

    type_value = schema.get("type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, Sequence):
        return {entry for entry in type_value if isinstance(entry, str)}
    return set()


def _resolve_schema_for_defaults(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the schema branch that best describes the expected type."""

    if _extract_type_set(schema):
        return schema
    for composite_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(composite_key)
        if isinstance(options, Sequence):
            for option in options:
                if isinstance(option, Mapping) and _extract_type_set(option):
                    return option
    return schema


def _default_for_schema(schema: Mapping[str, Any]) -> Any:
    """Return a neutral default value compatible with ``schema``."""

    resolved = _resolve_schema_for_defaults(schema)
    types = _extract_type_set(resolved)
    allows_null = "null" in types

    if "object" in types:
        return {}
    if "array" in types:
        return []
    if "integer" in types:
        return None if allows_null else 0
    if "number" in types:
        return None if allows_null else 0.0
    if "boolean" in types:
        return None if allows_null else False
    if "string" in types:
        return ""
    return None


def _coerce_enum_value(schema: Mapping[str, Any], value: Any) -> Any:
    """Return ``value`` adjusted to fit enum constraints when present."""

    resolved = _resolve_schema_for_defaults(schema)
    enum_values = resolved.get("enum")
    if not isinstance(enum_values, Sequence) or isinstance(enum_values, (str, bytes, bytearray)):
        return value
    allowed_values = [entry for entry in enum_values if not isinstance(entry, Mapping)]
    if not allowed_values:
        return value
    if value in allowed_values:
        return value
    return allowed_values[0]


def _has_valid_type(value: Any, types: set[str]) -> bool:
    if "object" in types and isinstance(value, Mapping):
        return True
    if "array" in types and isinstance(value, list):
        return True
    if "string" in types and isinstance(value, str):
        return True
    if "integer" in types and isinstance(value, int) and not isinstance(value, bool):
        return True
    if "number" in types and isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if "boolean" in types and isinstance(value, bool):
        return True
    return False


def _ensure_required_fields(schema: Mapping[str, Any], payload: MutableMapping[str, Any]) -> None:
    """Recursively insert defaults for required fields missing in ``payload``."""

    resolved_schema = _resolve_schema_for_defaults(schema)
    required_fields = resolved_schema.get("required")
    properties = resolved_schema.get("properties") if isinstance(resolved_schema, Mapping) else None
    if not isinstance(required_fields, Sequence):
        required_fields = []
    if not isinstance(properties, Mapping):
        properties = {}

    for field in required_fields:
        if not isinstance(field, str):
            continue
        field_schema = properties.get(field, {}) if isinstance(properties, Mapping) else {}
        field_schema_resolved = _resolve_schema_for_defaults(field_schema)
        field_types = _extract_type_set(field_schema_resolved)
        allows_null = "null" in field_types

        existing = payload.get(field, _MISSING)
        if existing is _MISSING:
            default_value = _default_for_schema(field_schema_resolved)
            payload[field] = default_value
            if isinstance(default_value, MutableMapping):
                _ensure_required_fields(field_schema_resolved, default_value)
            continue
        if existing is None and allows_null:
            continue
        if existing is None or (field_types and not _has_valid_type(existing, field_types)):
            default_value = _default_for_schema(field_schema_resolved)
            payload[field] = default_value
            if isinstance(default_value, MutableMapping):
                _ensure_required_fields(field_schema_resolved, default_value)
            continue

        coerced_value = _coerce_enum_value(field_schema_resolved, existing)
        if coerced_value is not existing:
            payload[field] = coerced_value
            existing = coerced_value

        if isinstance(existing, MutableMapping):
            _ensure_required_fields(field_schema_resolved, existing)
        elif isinstance(existing, Mapping):
            nested = dict(existing)
            payload[field] = nested
            _ensure_required_fields(field_schema_resolved, nested)
        elif isinstance(existing, list):
            items_schema = field_schema_resolved.get("items") if isinstance(field_schema_resolved, Mapping) else None
            if isinstance(items_schema, Mapping):
                for index, item in enumerate(existing):
                    if isinstance(item, MutableMapping):
                        _ensure_required_fields(items_schema, item)
                    elif isinstance(item, Mapping):
                        nested_item = dict(item)
                        existing[index] = nested_item
                        _ensure_required_fields(items_schema, nested_item)


def _ensure_required_profile_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``payload`` with required schema fields present."""

    normalized_payload = dict(payload)
    schema = _load_need_analysis_schema()
    if not schema:
        return normalized_payload
    if isinstance(schema, Mapping):
        _ensure_required_fields(schema, normalized_payload)
    return normalized_payload


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


def _parse_company_numbers(value: str) -> tuple[int, int | None] | None:
    match = _COMPANY_SIZE_NUMBER_RE.findall(value)
    if not match:
        return None
    if len(match) == 1:
        number = _coerce_company_size_token(match[0])
        if number is None:
            return None
        return number, None
    first = _coerce_company_size_token(match[0])
    second = _coerce_company_size_token(match[1])
    if first is None:
        return None
    if second is None:
        return (first, None)
    first, second = sorted((first, second))
    if second == first:
        second = None
    return first, second


def normalize_company_size(value: str | None) -> str:
    """Return a simplified employee count range when possible."""

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
    first, second = numbers
    if second is not None and second >= first:
        return f"{first}-{second}"
    suffix = "+" if plus else ""
    return f"{first}{suffix}"


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
    "business_context.industry_codes",
    "business_context.compliance_flags",
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
    "company.benefits",
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
    requirements = normalized.get("requirements")
    if isinstance(requirements, Mapping):
        requirements_dict = dict(requirements)
        requirements_dict["skill_mappings"] = build_skill_mappings(requirements_dict)
        normalized["requirements"] = requirements_dict
    return normalized


def _validate_profile_payload(
    payload: Mapping[str, Any],
) -> tuple[NormalizedProfilePayload | None, ValidationError | None]:
    """Validate ``payload`` against :class:`NeedAnalysisProfile`."""

    from models.need_analysis import NeedAnalysisProfile as _Profile

    candidate = dict(payload)
    normalize_interview_stages_field(candidate)

    try:
        model = _Profile.model_validate(candidate)
    except ValidationError as exc:
        return None, exc
    normalized_payload = cast(NormalizedProfilePayload, model.model_dump())
    return normalized_payload, None


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

    try:
        repaired = repair_profile_payload(payload, errors=errors)
    except Exception:
        logger.exception("JSON repair helper raised unexpectedly during normalization")
        return None

    if not repaired:
        return None
    if not isinstance(repaired, Mapping):
        return None
    normalized_repair = _normalize_profile_mapping(repaired)
    return normalized_repair


def normalize_profile(
    profile: Mapping[str, Any] | "NeedAnalysisProfile",
) -> NormalizedProfilePayload:
    """Return a validated, cleaned dictionary representation of ``profile``.

    The helper cleans scalar strings, deduplicates list entries, harmonises
    known fields (job title, city, country, branding metadata) and re-validates
    the resulting payload. If normalisation yields an invalid payload, it uses
    the OpenAI JSON repair fallback to recover when available.
    """

    model_dump: NormalizedProfilePayload | None = None
    data: Mapping[str, Any]
    is_model_input = hasattr(profile, "model_dump")
    if is_model_input:
        model_input = cast("NeedAnalysisProfile", profile)
        model_dump = cast(NormalizedProfilePayload, model_input.model_dump())
        data = model_dump
    elif isinstance(profile, Mapping):
        data = dict(profile)
    else:  # pragma: no cover - defensive branch
        raise TypeError("profile must be a mapping or NeedAnalysisProfile instance")

    normalized = _normalize_profile_mapping(data)
    normalized = _ensure_required_profile_fields(normalized)

    if is_model_input and normalized == data:
        assert model_dump is not None
        return model_dump

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
        assert model_dump is not None
        logger.warning(
            "Normalization produced invalid payload; returning original model dump.",
        )
        return model_dump

    logger.warning(
        "Normalization could not validate payload; returning NeedAnalysisProfile defaults.",
    )
    default_model, _ = _validate_profile_payload({})
    if default_model is not None:
        return default_model
    from models.need_analysis import NeedAnalysisProfile as _Profile  # local import to avoid cycles

    return cast(NormalizedProfilePayload, _Profile().model_dump())


__all__ = [
    "normalize_profile",
    "normalize_company_size",
    "extract_company_size",
    "extract_company_size_snippet",
    "_normalize_profile_mapping",
    "_attempt_llm_repair",
]
