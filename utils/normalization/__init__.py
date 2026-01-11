"""Backwards-compatible normalization API surface."""

from __future__ import annotations

from utils.normalization_payloads import (
    BusinessContextPayload,
    CompanyPayload,
    CompensationPayload,
    DepartmentPayload,
    EmploymentPayload,
    LocationPayload,
    MetaPayload,
    NormalizedProfilePayload,
    PhasePayload,
    PositionPayload,
    ProcessPayload,
    RequirementsPayload,
    ResponsibilitiesPayload,
    SkillEntryPayload,
    SkillMappingsPayload,
    StakeholderPayload,
    TeamPayload,
)

from .contact_normalization import normalize_phone_number, normalize_website_url
from .geo_normalization import (
    country_to_iso2,
    normalize_city_name,
    normalize_country,
    normalize_language,
    normalize_language_list,
)
from .profile_normalization import (
    _attempt_llm_repair,
    _normalize_profile_mapping,
    extract_company_size,
    extract_company_size_snippet,
    normalize_company_size,
    normalize_profile,
)
from .responsibility_classifier import (
    BulletCategory,
    categorize_bullet,
    classify_bullets,
    contains_optional_hint,
    looks_like_requirement,
    looks_like_responsibility,
)

__all__ = [
    "normalize_country",
    "country_to_iso2",
    "normalize_language",
    "normalize_language_list",
    "normalize_city_name",
    "normalize_phone_number",
    "normalize_website_url",
    "normalize_company_size",
    "extract_company_size",
    "extract_company_size_snippet",
    "normalize_profile",
    "classify_bullets",
    "categorize_bullet",
    "contains_optional_hint",
    "looks_like_requirement",
    "looks_like_responsibility",
    "BulletCategory",
    "NormalizedProfilePayload",
    "BusinessContextPayload",
    "CompanyPayload",
    "PositionPayload",
    "DepartmentPayload",
    "TeamPayload",
    "LocationPayload",
    "ResponsibilitiesPayload",
    "RequirementsPayload",
    "EmploymentPayload",
    "CompensationPayload",
    "ProcessPayload",
    "MetaPayload",
    "SkillMappingsPayload",
    "SkillEntryPayload",
    "StakeholderPayload",
    "PhasePayload",
    "_normalize_profile_mapping",
    "_attempt_llm_repair",
]
