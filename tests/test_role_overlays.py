from __future__ import annotations

import json
from pathlib import Path

from question_logic import _load_role_field_map, _resolve_role_questions
from wizard.planner.role_overlays import (
    ROLE_OVERLAY_FALLBACKS,
    canonicalize_role_key,
    get_role_overlay_questions,
)


def test_role_aliases_canonicalize_legacy_keys() -> None:
    assert canonicalize_role_key("Sales, marketing and public relations professionals") == (
        "esco_group:sales_marketing_pr_professionals"
    )
    assert canonicalize_role_key("software developers") == "esco_occ:software_developers"


def test_role_questions_resolve_from_overlay_registry() -> None:
    questions = _resolve_role_questions("software developers", lang="en")
    fields = {question["field"] for question in questions}
    assert "requirements.hard_skills_required" in fields
    assert "responsibilities.items" in fields


def test_role_field_map_uses_canonical_keys() -> None:
    role_field_map = _load_role_field_map()
    assert "esco_group:ict_professionals" in role_field_map
    assert "information and communications technology professionals" not in role_field_map


def test_role_field_map_entries_have_overlay_or_documented_fallback() -> None:
    payload = json.loads(Path("role_field_map.json").read_text(encoding="utf-8"))
    for raw_key in payload:
        canonical_key = canonicalize_role_key(raw_key)
        assert canonical_key, f"Role key '{raw_key}' must normalize to a canonical key"
        has_overlay = bool(get_role_overlay_questions(canonical_key))
        has_fallback = canonical_key in ROLE_OVERLAY_FALLBACKS
        assert has_overlay or has_fallback, (
            f"Role '{raw_key}' ({canonical_key}) needs overlays or a documented fallback"
        )
