from __future__ import annotations

from collections.abc import Mapping
from types import ModuleType
from typing import Any

import streamlit as st

from constants.keys import StateKeys, UIKeys
from utils.i18n import tr
from wizard.navigation_types import WizardContext

__all__ = ["step_landing"]


def _get_flow_module() -> ModuleType:
    """Return the lazily imported ``wizard.flow`` module."""

    from wizard import flow as wizard_flow

    return wizard_flow


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
    flow = _get_flow_module()
    flow._maybe_run_extraction(dict(context.schema))

    lang = st.session_state.get("lang", "de")
    prefill = st.session_state.pop("__prefill_profile_text__", None)
    if prefill is not None:
        st.session_state[UIKeys.PROFILE_TEXT_INPUT] = prefill
        st.session_state[StateKeys.RAW_TEXT] = prefill
        doc_prefill = st.session_state.get("__prefill_profile_doc__")
        if doc_prefill:
            st.session_state[StateKeys.RAW_BLOCKS] = doc_prefill.blocks

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

    if st.session_state.get("source_error"):
        fallback_message = tr(
            "Es gab ein Problem beim Import. Versuche URL oder Upload erneut oder kontaktiere unser Support-Team.",
            "There was an issue while importing the content. Retry the URL/upload or contact our support team.",
            lang=lang,
        )
        error_text = st.session_state.get("source_error_message") or fallback_message
        st.error(error_text)

    extraction_summary = st.session_state.get(StateKeys.EXTRACTION_SUMMARY)
    if isinstance(extraction_summary, str) and extraction_summary.strip() and not st.session_state.get("source_error"):
        st.info(extraction_summary)

    st.markdown("<div id='onboarding-source-inputs'></div>", unsafe_allow_html=True)
    st.markdown("<div class='onboarding-source-inputs'>", unsafe_allow_html=True)
    url_column, or_column, upload_column = st.columns([1, 0.18, 1], gap="large")
    with url_column:
        st.markdown("<div class='onboarding-source__panel'>", unsafe_allow_html=True)
        st.text_input(
            tr("Stellenanzeigen-URL hinzufügen", "Add the job posting URL", lang=lang),
            key=UIKeys.PROFILE_URL_INPUT,
            on_change=flow.on_url_changed,
            placeholder=tr("Stellenanzeigen-URL eingeben", "Enter the job posting URL", lang=lang),
            help=tr(
                "Die URL muss ohne Login erreichbar sein. Wir übernehmen den Inhalt automatisch.",
                "The URL needs to be accessible without authentication. We will fetch the content automatically.",
                lang=lang,
            ),
        )
        st.caption(
            tr(
                "Für öffentliche Karriereseiten oder Jobbörsen.",
                "Best for public career pages or job boards.",
                lang=lang,
            )
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with or_column:
        st.markdown(
            f"<div class='onboarding-source__or'><span>{tr('oder', 'or', lang=lang)}</span></div>",
            unsafe_allow_html=True,
        )

    with upload_column:
        st.markdown("<div class='onboarding-source__panel'>", unsafe_allow_html=True)
        st.file_uploader(
            tr("Stellenanzeige hochladen (PDF/DOCX/TXT)", "Upload the job posting (PDF/DOCX/TXT)", lang=lang),
            type=["pdf", "docx", "txt"],
            key=UIKeys.PROFILE_FILE_UPLOADER,
            on_change=flow.on_file_uploaded,
            help=tr(
                "Nach dem Upload starten wir sofort die Analyse.",
                "We start the analysis right after the upload finishes.",
                lang=lang,
            ),
        )
        st.caption(
            tr(
                "Ideal für interne Dokumente oder passwortgeschützte Dateien.",
                "Ideal for internal documents or files behind a login.",
                lang=lang,
            )
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    manual_text = st.text_area(
        tr("Stellenanzeige als Freitext", "Job posting as free text", lang=lang),
        key=UIKeys.PROFILE_TEXT_INPUT,
        value=str(st.session_state.get(UIKeys.PROFILE_TEXT_INPUT, st.session_state.get(StateKeys.RAW_TEXT, "")) or ""),
        placeholder=tr(
            "Füge hier den Inhalt der Stellenanzeige ein.",
            "Paste the job posting content here.",
            lang=lang,
        ),
        height=170,
    )
    if st.button(tr("Freitext analysieren", "Analyze free text", lang=lang), key="landing.analyze_free_text"):
        cleaned_text = manual_text.strip()
        st.session_state[StateKeys.RAW_TEXT] = cleaned_text
        st.session_state["__prefill_profile_text__"] = cleaned_text
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        st.session_state["__run_extraction__"] = True
        st.rerun()

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
