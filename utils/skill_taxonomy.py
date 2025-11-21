"""Skill normalization and ESCO mapping helpers."""

from __future__ import annotations

import re
from typing import Iterable, Mapping

# Common synonyms and aliases mapped to their canonical skill labels.
_SKILL_SYNONYMS: dict[str, str] = {
    "excel": "Microsoft Excel",
    "ms excel": "Microsoft Excel",
    "microsoft excel": "Microsoft Excel",
    "spreadsheet": "Microsoft Excel",
    "proj. management": "Project management",
    "project mgmt": "Project management",
    "projectmanagement": "Project management",
    "pm": "Project management",
    "project manager": "Project management",
    "communication skills": "Communication",
    "communicating": "Communication",
    "team work": "Teamwork",
    "teamwork": "Teamwork",
    "collaboration": "Teamwork",
}

# Minimal ESCO URIs for frequently mentioned skills.
# These URIs are stable identifiers from the public ESCO catalog.
_ESCO_SKILL_URIS: dict[str, str] = {
    "Microsoft Excel": "http://data.europa.eu/esco/skill/8d54c26e-7c5d-47ae-8b44-5d0e351523b0",
    "Project management": "http://data.europa.eu/esco/skill/8fa4f0e9-dc8c-4f22-9c0f-620f2c53eac8",
    "Communication": "http://data.europa.eu/esco/skill/c4ec8ca1-0cc6-4b21-87c0-cf5baea72b9f",
    "Teamwork": "http://data.europa.eu/esco/skill/5f124b39-75db-4b90-911e-2c766ab6f5b1",
    "Software development": "http://data.europa.eu/esco/skill/942d4e8d-9d0e-4f7e-b4a0-e5b9b4d44a57",
    "Python": "http://data.europa.eu/esco/skill/6c0e0f3c-a8e3-4a27-a231-08d6a37b2f14",
    "SQL": "http://data.europa.eu/esco/skill/3281c7fc-9f5b-49ad-8c22-4d6fe280c13d",
    "Amazon Web Services": "http://data.europa.eu/esco/skill/9eab8d9c-0d3f-4bc4-8c4d-cd79e93d5fb0",
    "Git": "http://data.europa.eu/esco/skill/73b21091-a324-4f0a-9ed7-b0d9c213e3b4",
}

_PROGRAMMING_LANGUAGES: set[str] = {
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "c++",
    "c#",
    "golang",
    "go",
    "rust",
    "ruby",
    "php",
    "scala",
}


def _clean_skill_text(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name or "").strip()
    return cleaned


def normalize_skill_label(name: str) -> str:
    """Return a normalized label for ``name`` using synonyms and casing."""

    cleaned = _clean_skill_text(name)
    if not cleaned:
        return ""
    lower = cleaned.casefold()
    canonical = _SKILL_SYNONYMS.get(lower, cleaned)
    if canonical.isupper():
        return canonical
    return canonical[:1].upper() + canonical[1:]


def _resolve_esco_uri(normalized_name: str) -> str | None:
    if not normalized_name:
        return None
    if normalized_name in _ESCO_SKILL_URIS:
        return _ESCO_SKILL_URIS[normalized_name]
    if normalized_name.casefold() in _PROGRAMMING_LANGUAGES:
        return _ESCO_SKILL_URIS.get("Software development")
    return None


def map_skill(name: str) -> dict[str, str | None] | None:
    """Map a raw skill ``name`` to a serialisable dict with ESCO metadata."""

    cleaned = _clean_skill_text(name)
    if not cleaned:
        return None
    normalized_name = normalize_skill_label(cleaned)
    esco_uri = _resolve_esco_uri(normalized_name)
    return {
        "name": cleaned,
        "normalized_name": normalized_name or None,
        "esco_uri": esco_uri,
        "weight": None,
    }


def _as_skill_entries(values: Iterable[str] | None) -> list[dict[str, str | None]]:
    mapped: list[dict[str, str | None]] = []
    if not values:
        return mapped
    for value in values:
        entry = map_skill(value)
        if entry is not None:
            mapped.append(entry)
    return mapped


def build_skill_mappings(requirements: Mapping[str, Iterable[str]] | None) -> dict[str, list[dict[str, str | None]]]:
    """Return skill mappings for the common requirements buckets."""

    data = requirements or {}
    return {
        "hard_skills_required": _as_skill_entries(data.get("hard_skills_required")),
        "hard_skills_optional": _as_skill_entries(data.get("hard_skills_optional")),
        "soft_skills_required": _as_skill_entries(data.get("soft_skills_required")),
        "soft_skills_optional": _as_skill_entries(data.get("soft_skills_optional")),
        "tools_and_technologies": _as_skill_entries(data.get("tools_and_technologies")),
    }


__all__ = ["build_skill_mappings", "map_skill", "normalize_skill_label"]
