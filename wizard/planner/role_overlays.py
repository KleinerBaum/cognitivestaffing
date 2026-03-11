from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class RoleQuestionEntry(TypedDict):
    field: str
    text_key: str


class RoleOverlay(TypedDict):
    aliases: list[str]
    questions: list[RoleQuestionEntry]


ROLE_KEY_ALIASES: dict[str, str] = {
    "information and communications technology professionals": "esco_group:ict_professionals",
    "health professionals": "esco_group:health_professionals",
    "sales, marketing and public relations professionals": "esco_group:sales_marketing_pr_professionals",
}

ROLE_OVERLAY_FALLBACKS: dict[str, str] = {
    "esco_group:ict_professionals": "Uses ESCO skill suggestions + role_field_map enrichment when no occupation-specific overlay is available.",
    "esco_group:health_professionals": "Uses ESCO skill suggestions + role_field_map enrichment until dedicated health group overlays are added.",
}


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, RoleOverlay]:
    registry_path = Path(__file__).resolve().parents[2] / "questions" / "overlays" / "role_questions.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    roles = payload.get("roles", {})
    if not isinstance(roles, dict):
        return {}
    loaded: dict[str, RoleOverlay] = {}
    for canonical_key, entry in roles.items():
        if not isinstance(entry, dict):
            continue
        aliases = [str(alias).strip() for alias in entry.get("aliases", []) if str(alias).strip()]
        questions: list[RoleQuestionEntry] = []
        for question in entry.get("questions", []):
            if not isinstance(question, dict):
                continue
            field = str(question.get("field") or "").strip()
            text_key = str(question.get("text_key") or "").strip()
            if not field or not text_key:
                continue
            questions.append({"field": field, "text_key": text_key})
        loaded[canonical_key] = {"aliases": aliases, "questions": questions}
    return loaded


@lru_cache(maxsize=1)
def role_aliases() -> dict[str, str]:
    aliases = dict(ROLE_KEY_ALIASES)
    for canonical_key, entry in _load_registry().items():
        aliases[canonical_key.casefold()] = canonical_key
        for alias in entry["aliases"]:
            aliases[alias.casefold()] = canonical_key
    return aliases


def canonicalize_role_key(raw_key: str) -> str:
    key = str(raw_key or "").strip().casefold()
    if not key:
        return ""
    return role_aliases().get(key, key)


def get_role_overlay_questions(raw_key: str) -> list[RoleQuestionEntry]:
    canonical_key = canonicalize_role_key(raw_key)
    if not canonical_key:
        return []
    overlay = _load_registry().get(canonical_key)
    if not overlay:
        return []
    return list(overlay["questions"])
