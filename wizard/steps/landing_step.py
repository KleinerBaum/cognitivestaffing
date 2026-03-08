from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

from constants.keys import StateKeys
from utils.i18n import tr
from wizard.navigation_types import WizardContext

__all__ = ["step_landing"]


def _parse_multiline_items(raw: str) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for line in raw.splitlines():
        value = line.strip()
        if not value:
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(value)
    return items


def _get_nested_string(profile: Mapping[str, Any], *path: str) -> str:
    current: Any = profile
    for key in path:
        if not isinstance(current, Mapping):
            return ""
        current = current.get(key)
    return current if isinstance(current, str) else ""


def _join_lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return ""


def step_landing(context: WizardContext) -> None:
    lang = st.session_state.get("lang", "de")
    profile_raw = st.session_state.get(StateKeys.PROFILE, {})
    profile = profile_raw if isinstance(profile_raw, Mapping) else {}

    st.header(tr("Willkommen", "Welcome", lang=lang))
    st.markdown(
        tr(
            "Starte mit den wichtigsten Eckdaten zur Rolle. Diese Angaben helfen uns, den weiteren Ablauf passend vorzubereiten.",
            "Start with the key role essentials. These inputs help us tailor the rest of the workflow.",
            lang=lang,
        )
    )

    job_title = st.text_input(
        tr("Jobtitel", "Job title", lang=lang),
        value=_get_nested_string(profile, "position", "job_title"),
        key="landing.position.job_title",
    )
    city = st.text_input(
        tr("Standort (Stadt)", "Location (city)", lang=lang),
        value=_get_nested_string(profile, "location", "primary_city"),
        key="landing.location.city",
    )

    tasks_raw = st.text_area(
        tr("Aufgaben (eine pro Zeile)", "Tasks (one item per line)", lang=lang),
        key="landing.responsibilities.items",
        value=_join_lines(
            profile.get("responsibilities", {}).get("items")
            if isinstance(profile.get("responsibilities"), Mapping)
            else []
        ),
        height=140,
    )
    skills_raw = st.text_area(
        tr("Skills (eine pro Zeile)", "Skills (one item per line)", lang=lang),
        key="landing.requirements.hard_skills_required",
        value=_join_lines(
            profile.get("requirements", {}).get("hard_skills_required")
            if isinstance(profile.get("requirements"), Mapping)
            else []
        ),
        height=140,
    )
    benefits_raw = st.text_area(
        tr("Benefits (eine pro Zeile)", "Benefits (one item per line)", lang=lang),
        key="landing.compensation.benefits",
        value=_join_lines(
            profile.get("compensation", {}).get("benefits") if isinstance(profile.get("compensation"), Mapping) else []
        ),
        height=140,
    )

    can_continue = bool(job_title.strip() and city.strip())
    if st.button(
        tr("Weiter", "Continue", lang=lang),
        key="landing.continue",
        disabled=not can_continue,
        type="primary",
    ):
        context.update_profile("position.job_title", job_title.strip())
        context.update_profile("location.primary_city", city.strip())
        context.update_profile("responsibilities.items", _parse_multiline_items(tasks_raw))
        context.update_profile("requirements.hard_skills_required", _parse_multiline_items(skills_raw))
        context.update_profile("compensation.benefits", _parse_multiline_items(benefits_raw))
        context.next_step()
