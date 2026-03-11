"""Shared helpers for Wizard V2 step renderers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import streamlit as st

from constants.keys import StateKeys
from wizard.navigation_types import WizardContext
from utils.i18n import tr


LocalizedPair = tuple[str, str]
QuestionItem = dict[str, str]


def render_v2_step(
    *,
    context: WizardContext,
    missing_paths: Sequence[str] | None = None,
    step_key: str | None = None,
) -> tuple[str, ...]:
    """Resolve required fields for the active V2 step.

    ``missing_paths`` can explicitly override the registry-based required fields.
    """

    del context
    if missing_paths is not None:
        return tuple(missing_paths)

    active_step = step_key or st.session_state.get(StateKeys.WIZARD_LAST_STEP)
    if not isinstance(active_step, str) or not active_step:
        return ()

    from wizard.step_registry_v2 import get_step_v2

    definition = get_step_v2(active_step)
    if definition is None:
        return ()
    return tuple(definition.required_fields)


def get_profile_data() -> dict[str, Any]:
    """Return a mutable profile dict from Streamlit session state."""

    profile = st.session_state.get(StateKeys.PROFILE, {})
    if isinstance(profile, dict):
        return profile
    return {}


def get_value(data: Mapping[str, Any], path: str) -> Any:
    """Resolve a dotted ``path`` from ``data``."""

    cursor: Any = data
    for part in path.split("."):
        if isinstance(cursor, Mapping):
            cursor = cursor.get(part)
        else:
            return None
    return cursor


def set_value(data: dict[str, Any], path: str, value: Any) -> None:
    """Set ``value`` into ``data`` at dotted ``path``."""

    cursor: dict[str, Any] = data
    parts = path.split(".")
    for part in parts[:-1]:
        nested = cursor.get(part)
        if not isinstance(nested, dict):
            nested = {}
            cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value


def value_missing(value: Any) -> bool:
    """Return ``True`` when ``value`` should be treated as missing."""

    return value in (None, "", [], {})


def parse_multiline(value: str) -> list[str]:
    """Split multiline/comma-separated entries into a normalized list."""

    entries = [item.strip() for part in value.splitlines() for item in part.split(",")]
    return [item for item in entries if item]


def pretty_value(value: Any) -> str:
    """Render compact preview text for summary chips."""

    if isinstance(value, list):
        if not value:
            return tr("Nicht gesetzt", "Not set")
        if len(value) == 1:
            return str(value[0])
        return f"{value[0]} +{len(value) - 1}"
    if isinstance(value, dict):
        return tr("Objekt", "Object")
    if value_missing(value):
        return tr("Nicht gesetzt", "Not set")
    return str(value)


def render_summary_chips(summary_fields: Sequence[str], profile: Mapping[str, Any]) -> None:
    """Render summary fields for the active V2 step as compact chips."""

    if not summary_fields:
        return

    chip_items: list[str] = []
    for path in summary_fields:
        value = pretty_value(get_value(profile, path))
        chip_items.append(f"<span class='wiz-v2-chip'><strong>{path}</strong>: {value}</span>")

    st.markdown(
        """
        <style>
            .wiz-v2-chip-wrap { display:flex; flex-wrap:wrap; gap: .45rem; margin:.2rem 0 .6rem 0; }
            .wiz-v2-chip { border:1px solid rgba(148,163,184,.45); border-radius:999px; padding:.2rem .6rem; font-size:.78rem; background:rgba(15,23,42,.03); }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='wiz-v2-chip-wrap'>{''.join(chip_items)}</div>", unsafe_allow_html=True)


def _question_rank(priority: str) -> int:
    normalized = priority.strip().lower()
    if normalized in {"critical", "blocking"}:
        return 0
    if normalized == "normal":
        return 1
    return 2


def collect_top_questions(
    *,
    profile: Mapping[str, Any],
    required_paths: Sequence[str],
    followup_prefixes: Sequence[str],
    limit: int = 3,
) -> tuple[list[QuestionItem], list[QuestionItem]]:
    """Build prioritized top-questions + optional remainder from missing/follow-ups."""

    questions: list[QuestionItem] = []
    for path in required_paths:
        if value_missing(get_value(profile, path)):
            questions.append(
                {
                    "field": path,
                    "question": tr(f"Bitte ausfüllen: {path}", f"Please provide: {path}"),
                    "priority": "critical",
                }
            )

    raw_followups = st.session_state.get(StateKeys.FOLLOWUPS, [])
    if isinstance(raw_followups, list):
        for item in raw_followups:
            if not isinstance(item, Mapping):
                continue
            field = str(item.get("field") or "").strip()
            if not field:
                continue
            if not any(field.startswith(prefix) for prefix in followup_prefixes):
                continue
            if not value_missing(get_value(profile, field)):
                continue
            questions.append(
                {
                    "field": field,
                    "question": str(item.get("question") or field),
                    "priority": str(item.get("priority") or "normal"),
                }
            )

    deduped: dict[str, QuestionItem] = {}
    for question in questions:
        existing = deduped.get(question["field"])
        if existing is None or _question_rank(question["priority"]) < _question_rank(existing["priority"]):
            deduped[question["field"]] = question

    ordered = sorted(deduped.values(), key=lambda item: (_question_rank(item["priority"]), item["field"]))
    return ordered[:limit], ordered[limit:]


def render_question_cards(questions: Iterable[QuestionItem]) -> None:
    """Render visual cards for follow-up/missing questions."""

    for index, question in enumerate(questions, start=1):
        priority = question["priority"].strip().lower()
        icon = "⚠️" if priority in {"critical", "blocking"} else "🛈"
        st.markdown(f"**{index}. {icon} {question['question']}**")
        st.caption(f"`{question['field']}` · {priority}")


def collect_followup_questions(*, profile: Mapping[str, Any], followup_prefixes: Sequence[str]) -> list[QuestionItem]:
    """Return unresolved follow-up questions for the given step prefixes."""

    raw_followups = st.session_state.get(StateKeys.FOLLOWUPS, [])
    if not isinstance(raw_followups, list):
        return []
    items: list[QuestionItem] = []
    for item in raw_followups:
        if not isinstance(item, Mapping):
            continue
        field = str(item.get("field") or "").strip()
        if not field or not any(field.startswith(prefix) for prefix in followup_prefixes):
            continue
        if not value_missing(get_value(profile, field)):
            continue
        items.append(
            {
                "field": field,
                "question": str(item.get("question") or field),
                "priority": str(item.get("priority") or "normal"),
            }
        )
    return sorted(items, key=lambda question: (_question_rank(question["priority"]), question["field"]))


def commit_profile(
    profile: dict[str, Any],
    updates: Mapping[str, Any],
    *,
    context_update: Callable[[str, Any], None] | None,
) -> None:
    """Apply updates to profile data and persist to ``StateKeys.PROFILE``."""

    for path, value in updates.items():
        set_value(profile, path, value)
        if context_update is not None:
            context_update(path, value)
    st.session_state[StateKeys.PROFILE] = profile
