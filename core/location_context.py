"""Location normalization and policy overlays for follow-up and export workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from i18n import t as translate_key
from utils.normalization.geo_normalization import country_to_iso2, normalize_city_name, normalize_country

RemotePolicy = Literal["onsite", "hybrid", "remote", "flexible", "unknown"]
VisaPolicy = Literal["required", "available", "not_available", "unknown"]
RelocationPolicy = Literal["offered", "case_by_case", "not_offered", "unknown"]


_COUNTRY_OVERLAYS: dict[str, dict[str, Any]] = {
    "DE": {
        "currency": "EUR",
        "benefits": ["public_transport_support", "pension_contribution"],
    },
    "CH": {
        "currency": "CHF",
        "benefits": ["pension_contribution", "meal_allowance"],
    },
    "US": {
        "currency": "USD",
        "benefits": ["healthcare_plan", "equity_program"],
    },
    "DEFAULT": {"currency": "EUR", "benefits": []},
}


@dataclass(frozen=True)
class LocationContext:
    city: str
    region: str
    country: str
    country_code: str
    remote_policy: RemotePolicy
    visa_policy: VisaPolicy
    relocation_policy: RelocationPolicy
    compensation_currency: str
    benefits_overlay: tuple[str, ...]


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "ja", "1"}:
            return True
        if normalized in {"false", "no", "nein", "0"}:
            return False
    return None


def _normalize_remote_policy(value: object) -> RemotePolicy:
    text = str(value or "").strip().casefold()
    if not text:
        return "unknown"
    if "hybrid" in text:
        return "hybrid"
    if "remote" in text:
        return "remote"
    if "on" in text and "site" in text:
        return "onsite"
    if text in {"flex", "flexible"}:
        return "flexible"
    return "unknown"


def _visa_policy(value: object) -> VisaPolicy:
    parsed = _as_bool(value)
    if parsed is True:
        return "available"
    if parsed is False:
        return "not_available"
    return "unknown"


def _relocation_policy(value: object) -> RelocationPolicy:
    parsed = _as_bool(value)
    if parsed is True:
        return "offered"
    if parsed is False:
        return "not_offered"
    return "unknown"


def _get_in(data: Mapping[str, Any], path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def build_location_context(profile: Mapping[str, Any]) -> LocationContext:
    city_raw = _get_in(profile, "location.primary_city", "")
    region_raw = _get_in(profile, "location.region", "")
    country_raw = _get_in(profile, "location.country", "")
    work_policy_raw = _get_in(profile, "employment.work_policy", "")
    visa_raw = _get_in(profile, "employment.visa_sponsorship", None)
    relocation_raw = _get_in(profile, "employment.relocation_support", None)

    country = normalize_country(str(country_raw or "").strip()) or ""
    country_code = country_to_iso2(country) or ""
    overlay = _COUNTRY_OVERLAYS.get(country_code, _COUNTRY_OVERLAYS["DEFAULT"])

    return LocationContext(
        city=normalize_city_name(str(city_raw or "")) or "",
        region=str(region_raw or "").strip(),
        country=country,
        country_code=country_code,
        remote_policy=_normalize_remote_policy(work_policy_raw),
        visa_policy=_visa_policy(visa_raw),
        relocation_policy=_relocation_policy(relocation_raw),
        compensation_currency=str(overlay.get("currency") or ""),
        benefits_overlay=tuple(str(item) for item in overlay.get("benefits", []) if isinstance(item, str)),
    )


def is_location_field_optional(field: str, context: LocationContext) -> bool:
    if field == "location.primary_city" and context.remote_policy == "remote":
        return True
    if field in {"employment.visa_sponsorship", "employment.relocation_support"} and not context.country_code:
        return True
    return False


def location_sensitive_followups(profile: Mapping[str, Any], *, locale: str = "en") -> list[dict[str, Any]]:
    lang = "de" if (locale or "en").lower().startswith("de") else "en"
    context = build_location_context(profile)
    followups: list[dict[str, Any]] = []

    if not context.country:
        followups.append(
            {
                "field": "location.country",
                "question": translate_key("location_followups.country", lang),
                "priority": "critical",
            }
        )
    if context.remote_policy != "remote" and not context.city:
        followups.append(
            {
                "field": "location.primary_city",
                "question": translate_key("location_followups.city", lang),
                "priority": "normal",
            }
        )
    if context.visa_policy == "unknown" and context.country_code:
        followups.append(
            {
                "field": "employment.visa_sponsorship",
                "question": translate_key("location_followups.visa_sponsorship", lang),
                "priority": "normal",
            }
        )
    if context.relocation_policy == "unknown" and context.remote_policy in {"onsite", "hybrid"}:
        followups.append(
            {
                "field": "employment.relocation_support",
                "question": translate_key("location_followups.relocation", lang),
                "priority": "optional",
            }
        )

    return followups


__all__ = [
    "LocationContext",
    "RemotePolicy",
    "RelocationPolicy",
    "VisaPolicy",
    "build_location_context",
    "is_location_field_optional",
    "location_sensitive_followups",
]
