"""Rendering and utility helpers for follow-up questions."""

from __future__ import annotations

import sys
from datetime import date
from typing import Any, Callable, Collection, Final, Iterable, Literal, Mapping, Sequence, TypedDict

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from constants.keys import ProfilePaths, StateKeys, UIKeys
from utils.i18n import tr
from wizard.followups import followup_has_response
from wizard.metadata import FIELD_SECTION_MAP, PAGE_FOLLOWUP_PREFIXES, get_missing_critical_fields
from wizard.types import LangPair, LangSuggestionPair
from wizard._logic import _get_profile_state, get_in, set_in, _update_profile
from wizard.date_utils import default_date

JobAdGenerator = Callable[
    [
        Mapping[str, Any],
        Collection[str],
        str | None,
        Sequence[dict[str, str]],
        str | None,
        str,
        bool,
    ],
    bool,
]
InterviewGenerator = Callable[[Mapping[str, Any], str, int, str, bool, bool], bool]

REQUIRED_PREFIX: Final[str] = ":red[*] "
FOLLOWUP_STYLE_KEY: Final[str] = "_followup_styles_v1"

YES_NO_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED),
    str(ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT),
    str(ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP),
    str(ProfilePaths.EMPLOYMENT_OVERTIME_EXPECTED),
    str(ProfilePaths.EMPLOYMENT_SHIFT_WORK),
    str(ProfilePaths.EMPLOYMENT_SECURITY_CLEARANCE_REQUIRED),
    str(ProfilePaths.COMPENSATION_SALARY_PROVIDED),
}

DATE_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.META_TARGET_START_DATE),
    str(ProfilePaths.META_APPLICATION_DEADLINE),
    str(ProfilePaths.EMPLOYMENT_CONTRACT_END),
}

NUMBER_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.POSITION_TEAM_SIZE),
    str(ProfilePaths.POSITION_SUPERVISES),
    str(ProfilePaths.COMPENSATION_SALARY_MIN),
    str(ProfilePaths.COMPENSATION_SALARY_MAX),
    str(ProfilePaths.EMPLOYMENT_TRAVEL_SHARE),
}

LIST_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.RESPONSIBILITIES_ITEMS),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_LANGUAGES_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
    str(ProfilePaths.REQUIREMENTS_CERTIFICATIONS),
    str(ProfilePaths.REQUIREMENTS_CERTIFICATES),
    str(ProfilePaths.COMPENSATION_BENEFITS),
}

INLINE_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.COMPANY_NAME),
    str(ProfilePaths.COMPANY_CONTACT_NAME),
    str(ProfilePaths.COMPANY_CONTACT_EMAIL),
    str(ProfilePaths.COMPANY_CONTACT_PHONE),
    str(ProfilePaths.DEPARTMENT_NAME),
    str(ProfilePaths.LOCATION_PRIMARY_CITY),
    str(ProfilePaths.LOCATION_COUNTRY),
    str(ProfilePaths.META_TARGET_START_DATE),
    str(ProfilePaths.POSITION_JOB_TITLE),
    str(ProfilePaths.POSITION_REPORTING_MANAGER_NAME),
    str(ProfilePaths.POSITION_ROLE_SUMMARY),
    "responsibilities.items",
    "requirements.hard_skills_required",
    "requirements.soft_skills_required",
    str(ProfilePaths.TEAM_REPORTING_LINE),
}


class TargetedPromptConfig(TypedDict, total=False):
    """Configuration for inline critical field prompts."""

    prompt: LangPair
    description: LangPair
    suggestions: LangSuggestionPair
    style: Literal["info", "warning"]
    priority: Literal["critical", "normal"]


CRITICAL_FIELD_PROMPTS: dict[str, TargetedPromptConfig] = {
    "company.name": {
        "prompt": (
            "Wie lautet der offizielle Firmenname?",
            "What is the official company name?",
        ),
        "description": (
            "Bitte den rechtlichen oder bevorzugten Namen angeben, damit wir korrekt referenzieren können.",
            "Provide the legal or preferred name so we can reference the company correctly.",
        ),
        "suggestions": (
            ["Noch vertraulich", "Name wird nachgereicht"],
            ["Confidential for now", "Name to be confirmed"],
        ),
        "style": "warning",
    },
    "position.job_title": {
        "prompt": (
            "Welcher Jobtitel soll in der Ausschreibung stehen?",
            "What job title should appear in the posting?",
        ),
        "description": (
            "Ein klarer Jobtitel hilft der KI bei allen weiteren Vorschlägen.",
            "A clear job title helps the assistant with every downstream suggestion.",
        ),
        "suggestions": (
            ["Software Engineer", "Sales Manager", "Product Manager"],
            ["Software Engineer", "Sales Manager", "Product Manager"],
        ),
        "style": "info",
    },
    "position.role_summary": {
        "prompt": (
            "Wie würdest du die Rolle in 2-3 Sätzen beschreiben?",
            "How would you summarise the role in 2-3 sentences?",
        ),
        "description": (
            "Diese Kurzbeschreibung landet sowohl in Follow-ups als auch im Job-Ad-Entwurf.",
            "We use this short blurb in follow-ups and the job ad draft.",
        ),
        "suggestions": (
            [
                "Treibt den Aufbau datengetriebener Produkte voran",
                "Koordiniert funktionsübergreifende Projektteams",
            ],
            [
                "Drives the build-out of data-driven products",
                "Coordinates cross-functional project teams",
            ],
        ),
        "style": "info",
    },
    "location.country": {
        "prompt": (
            "In welchem Land ist die Rolle verortet?",
            "Which country is this role based in?",
        ),
        "description": (
            "Das Land steuert Gehaltsbenchmarks, Benefits und Sprachvorschläge.",
            "Country selection powers salary ranges, benefits, and language suggestions.",
        ),
        "suggestions": (
            ["Deutschland", "Österreich", "Schweiz"],
            ["Germany", "Austria", "Switzerland"],
        ),
        "style": "warning",
    },
    "company.contact_email": {
        "prompt": (
            "Welche E-Mail-Adresse sollen Kandidat:innen zur Kontaktaufnahme nutzen?",
            "Which email address should candidates use to reach you?",
        ),
        "description": (
            "Diese Adresse landet in Exporten und Follow-ups – bitte ein Postfach mit aktivem Monitoring angeben.",
            "This address is used in exports and follow-ups – please provide a monitored inbox.",
        ),
        "suggestions": (
            ["talent@firma.de", "jobs@unternehmen.com"],
            ["talent@company.com", "jobs@org.io"],
        ),
        "style": "warning",
    },
    "location.primary_city": {
        "prompt": (
            "In welcher Stadt arbeitet das Team überwiegend?",
            "Which city is the team primarily based in?",
        ),
        "description": (
            "Die Stadt hilft bei Gehaltsbandbreiten, Steuerungen für Zeitzonen und Office-Vorschlägen.",
            "Knowing the city informs salary bands, time zone handling, and office suggestions.",
        ),
        "suggestions": (
            ["Berlin", "München", "Remote (Berlin bevorzugt)"],
            ["Berlin", "Munich", "Remote (Berlin preferred)"],
        ),
        "style": "warning",
    },
    "requirements.hard_skills_required": {
        "prompt": (
            "Welche Hard Skills sind zwingend?",
            "Which hard skills are must-haves?",
        ),
        "description": (
            "Bitte Kerntechnologien oder Tools nennen – das fokussiert unsere Vorschläge.",
            "List the core technologies or tools so our suggestions stay focused.",
        ),
        "suggestions": (
            ["Python, SQL, ETL", "AWS, Terraform, CI/CD"],
            ["Python, SQL, ETL", "AWS, Terraform, CI/CD"],
        ),
        "style": "warning",
    },
    "requirements.soft_skills_required": {
        "prompt": (
            "Welche Soft Skills sind unverzichtbar?",
            "Which soft skills are non-negotiable?",
        ),
        "description": (
            "Stichworte reichen – wir übernehmen die Formulierung im Jobprofil.",
            "Short bullet points are enough – we will phrase them for the profile.",
        ),
        "suggestions": (
            [
                "Kommunikationsstark, teamorientiert, lösungsorientiert",
                "Selbstständig, proaktiv, kundenorientiert",
            ],
            [
                "Strong communicator, collaborative, solution-oriented",
                "Self-driven, proactive, customer-focused",
            ],
        ),
        "style": "info",
    },
}


def _normalize_followup_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    return []


def _ensure_followup_styles() -> None:
    if st.session_state.get(FOLLOWUP_STYLE_KEY):
        return
    st.session_state[FOLLOWUP_STYLE_KEY] = True
    st.markdown(
        """
        <style>
            .wizard-followup-card {
                background: var(--surface-0, rgba(226, 232, 240, 0.65));
                border-radius: 20px;
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.4));
                padding: 1.25rem 1.35rem;
                margin-top: 1rem;
                box-shadow: 0 12px 26px rgba(15, 23, 42, 0.16);
                animation: wizardFollowupCardIn 0.4s var(--transition-base, 0.18s ease-out) 1;
            }

            .wizard-followup-item {
                border-radius: 16px;
                padding: 0.85rem 1rem;
                background: var(--surface-1, rgba(255, 255, 255, 0.85));
                margin-bottom: 0.65rem;
                border: 1px solid transparent;
                opacity: 0;
                animation: wizardFollowupIn 0.5s ease forwards;
            }

            .wizard-followup-meta {
                color: rgba(15, 23, 42, 0.6);
                font-size: 0.85rem;
            }

            .fu-highlight {
                border-color: rgba(255, 0, 0, 0.25);
                box-shadow: 0 0 0 2px rgba(248, 113, 113, 0.3);
            }

            .fu-highlight-soft {
                border-color: rgba(59, 130, 246, 0.35);
                box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.35);
            }

            .wizard-followup-chip button {
                width: 100%;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_followup_suggestion(field: str, key: str, suggestion: str) -> None:
    normalized = suggestion.strip()
    if not normalized:
        return
    if field in YES_NO_FOLLOWUP_FIELDS:
        lowered = normalized.casefold()
        st.session_state[key] = lowered in {"yes", "ja", "true", "wahr", "1", "y"}
        st.session_state[f"{key}_touched"] = True
        return
    if field in DATE_FOLLOWUP_FIELDS:
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError:
            parsed = None
        st.session_state[key] = parsed if parsed is not None else normalized
        return
    if field in NUMBER_FOLLOWUP_FIELDS:
        cleaned = normalized.replace(",", ".")
        try:
            st.session_state[key] = int(float(cleaned))
        except ValueError:
            st.session_state[key] = normalized
        return
    if field in LIST_FOLLOWUP_FIELDS:
        current = str(st.session_state.get(key, "") or "")
        items = [line.strip() for line in current.splitlines() if line.strip()]
        if normalized not in items:
            items.append(normalized)
        st.session_state[key] = "\n".join(items)
        return
    st.session_state[key] = normalized


def _coerce_followup_number(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        try:
            return int(float(normalized))
        except ValueError:
            pass
    return 0


def _lang_index(lang: str | None) -> int:
    if not lang:
        return 0
    return 0 if lang.lower().startswith("de") else 1


def _select_lang_text(pair: LangPair | None, lang: str | None) -> str:
    if not pair:
        return ""
    idx = _lang_index(lang)
    return pair[idx] if idx < len(pair) else pair[0]


def _select_lang_suggestions(pair: LangSuggestionPair | None, lang: str | None) -> list[str]:
    if not pair:
        return []
    idx = _lang_index(lang)
    if idx >= len(pair):
        idx = 0
    return list(pair[idx])


def _ensure_targeted_followup(field: str) -> None:
    config = CRITICAL_FIELD_PROMPTS.get(field)
    if not config:
        return
    existing = list(st.session_state.get(StateKeys.FOLLOWUPS) or [])
    if any(q.get("field") == field for q in existing):
        return
    lang = getattr(st.session_state, "lang", None) or st.session_state.get(UIKeys.LANG_SELECT, "de")
    followup = {
        "field": field,
        "question": _select_lang_text(config.get("prompt"), lang),
        "priority": config.get("priority", "critical"),
        "suggestions": _select_lang_suggestions(config.get("suggestions"), lang),
    }
    description = _select_lang_text(config.get("description"), lang)
    if description:
        followup["description"] = description
    style = config.get("style")
    if style:
        followup["ui_variant"] = style
    existing.insert(0, followup)
    st.session_state[StateKeys.FOLLOWUPS] = existing


def _missing_fields_for_section(section_index: int) -> list[str]:
    extraction_missing = st.session_state.get(StateKeys.EXTRACTION_MISSING)
    computed_missing = get_missing_critical_fields()
    if extraction_missing:
        missing = list(dict.fromkeys((*extraction_missing, *computed_missing)))
    else:
        missing = computed_missing
    section_missing = [field for field in missing if FIELD_SECTION_MAP.get(field) == section_index]
    for field in section_missing:
        _ensure_targeted_followup(field)
    return section_missing


def _normalize_list_value(existing_value: Any) -> str:
    return "\n".join(_normalize_followup_list(existing_value))


def _default_date(existing_value: Any) -> date:
    return default_date(existing_value)


def _should_render_for_field(field: str, prefixes: Sequence[str], exact: bool) -> bool:
    if exact:
        return any(field == prefix for prefix in prefixes)
    return any(field.startswith(prefix) for prefix in prefixes)


def _resolve_followup_renderer() -> Callable[[dict, dict], None]:
    """Return the active follow-up renderer (patched via ``wizard.flow`` when needed)."""

    flow_module = sys.modules.get("wizard.flow")
    renderer = getattr(flow_module, "_render_followup_question", None) if flow_module else None
    if callable(renderer):
        return renderer
    return _render_followup_question


def _render_followup_question(q: dict, data: dict) -> None:
    profile_data = _get_profile_state()
    field = str(q.get("field", ""))
    if not field:
        return
    prompt = q.get("question", "")
    suggestions = [str(option).strip() for option in q.get("suggestions") or [] if str(option).strip()]
    key = f"fu_{field}"
    anchor = f"anchor_{key}"
    focus_sentinel = f"{key}_focus_pending"
    highlight_sentinel = f"{key}_highlight_pending"
    container = st.container()
    with container:
        st.markdown(f"<div id='{anchor}'></div>", unsafe_allow_html=True)
        st.markdown("<div class='wizard-followup-item'>", unsafe_allow_html=True)
    existing_value = get_in(profile_data, field, None)
    if key not in st.session_state:
        if field in LIST_FOLLOWUP_FIELDS:
            st.session_state[key] = _normalize_list_value(existing_value)
        elif field in YES_NO_FOLLOWUP_FIELDS:
            st.session_state[key] = bool(existing_value)
        elif field in DATE_FOLLOWUP_FIELDS:
            default_value = _default_date(existing_value)
            st.session_state[key] = default_value
        else:
            st.session_state[key] = str(existing_value or "")
    if focus_sentinel not in st.session_state:
        st.session_state[focus_sentinel] = True
    if highlight_sentinel not in st.session_state:
        st.session_state[highlight_sentinel] = True
    ui_variant = q.get("ui_variant")
    description = q.get("description")
    if ui_variant in ("info", "warning") and description:
        getattr(container, ui_variant)(description)
    elif description:
        container.caption(description)
    priority = q.get("priority")
    question_text = prompt or tr("Antwort eingeben", "Enter response")
    with container:
        if priority == "critical":
            st.markdown(f"{REQUIRED_PREFIX}**{question_text}**")
        else:
            st.markdown(f"**{question_text}**")
    if suggestions:
        cols = container.columns(len(suggestions))
        for index, (col, option) in enumerate(zip(cols, suggestions)):
            with col:
                st.markdown("<div class='wizard-followup-chip'>", unsafe_allow_html=True)
                st.button(
                    option,
                    key=f"{key}_opt_{index}",
                    on_click=_apply_followup_suggestion,
                    args=(field, key, option),
                )
                st.markdown("</div>", unsafe_allow_html=True)

    should_focus = bool(st.session_state.get(focus_sentinel, False))
    label_text = question_text
    processed_value: Any
    touched_key: str | None = None
    with container:
        if field in YES_NO_FOLLOWUP_FIELDS:
            touched_key = f"{key}_touched"
            if touched_key not in st.session_state:
                st.session_state[touched_key] = existing_value is not None

            def _mark_followup_touched() -> None:
                st.session_state[touched_key] = True

            checkbox_value = st.checkbox(
                label_text,
                key=key,
                label_visibility="collapsed",
                on_change=_mark_followup_touched,
            )
            processed_value = bool(checkbox_value) if st.session_state.get(touched_key) else None
        elif field in NUMBER_FOLLOWUP_FIELDS:
            numeric_default = _coerce_followup_number(existing_value)
            raw_state_value = st.session_state.get(key, numeric_default)
            numeric_initial = _coerce_followup_number(raw_state_value)
            numeric_value = st.number_input(
                label_text,
                key=key,
                value=float(numeric_initial),
                step=1.0,
                label_visibility="collapsed",
            )
            processed_value = (
                int(numeric_value) if isinstance(numeric_value, float) and numeric_value.is_integer() else numeric_value
            )
        elif field in DATE_FOLLOWUP_FIELDS:
            date_value = st.date_input(
                label_text,
                key=key,
                format="YYYY-MM-DD",
                label_visibility="collapsed",
            )
            processed_value = date_value.isoformat() if isinstance(date_value, date) else ""
        elif field in LIST_FOLLOWUP_FIELDS:
            text_value = st.text_area(
                label_text,
                key=key,
                label_visibility="collapsed",
                placeholder=tr(
                    "Bitte jede Angabe in einer eigenen Zeile ergänzen.",
                    "Add each entry on a separate line.",
                ),
                height=110,
            )
            processed_value = [line.strip() for line in text_value.splitlines() if line.strip()]
        else:
            processed_value = st.text_input(
                label_text,
                key=key,
                label_visibility="collapsed",
            )
        if should_focus:
            st.session_state[focus_sentinel] = False
        highlight_pending = st.session_state.get(highlight_sentinel, False)
        if highlight_pending:
            highlight_class = "fu-highlight" if priority == "critical" else "fu-highlight-soft"
            if priority == "critical":
                st.toast(
                    tr("Neue kritische Anschlussfrage", "New critical follow-up"),
                    icon="⚠️",
                )
            st.markdown(
                f"""
<script>
(function() {{
    const anchor = document.getElementById('{anchor}');
    if (!anchor) {{
        return;
    }}
    const wrapper = anchor.nextElementSibling;
    if (!wrapper) {{
        return;
    }}
    wrapper.classList.add('{highlight_class}');
    wrapper.scrollIntoView({{behavior:'smooth',block:'center'}});
    const focusable = wrapper.querySelector("input,textarea,select,button");
    if (focusable && focusable.focus) {{
        focusable.focus({{preventScroll: true}});
    }}
}})();
</script>
""",
                unsafe_allow_html=True,
            )
            st.session_state[highlight_sentinel] = False
    widget_has_state = field in st.session_state
    should_sync_widget_state = field not in INLINE_FOLLOWUP_FIELDS
    if widget_has_state:
        _update_profile(
            field,
            processed_value,
            session_value=processed_value,
            sync_widget_state=should_sync_widget_state,
        )
    else:
        _update_profile(
            field,
            processed_value,
            sync_widget_state=should_sync_widget_state,
        )
    if isinstance(data, dict):
        set_in(data, field, processed_value)
        followups_answered = get_in(profile_data, "meta.followups_answered")
        if followups_answered is not None:
            set_in(data, "meta.followups_answered", followups_answered)
    if followup_has_response(processed_value):
        st.session_state.pop(focus_sentinel, None)
        st.session_state.pop(highlight_sentinel, None)
        if touched_key is not None:
            st.session_state.pop(touched_key, None)
    container.markdown("</div>", unsafe_allow_html=True)


def _render_followups_for_section(
    prefixes: Iterable[str],
    data: dict,
    *,
    exact: bool = False,
    container: DeltaGenerator | None = None,
    container_factory: Callable[[], DeltaGenerator] | None = None,
) -> None:
    normalized_prefixes = tuple(str(prefix) for prefix in prefixes if prefix)
    if not normalized_prefixes:
        return

    followup_items: list[dict] = []
    pending = st.session_state.get(StateKeys.FOLLOWUPS, []) or []
    for question in pending:
        field = str(question.get("field", ""))
        if not field:
            continue
        if not _should_render_for_field(field, normalized_prefixes, exact):
            continue
        if not exact and field in INLINE_FOLLOWUP_FIELDS:
            continue
        followup_items.append(question)

    if followup_items:
        renderer = _resolve_followup_renderer()
        _ensure_followup_styles()
        target_container = container
        if target_container is None:
            target_container = container_factory() if container_factory else st.container()
        with target_container:
            st.markdown("<div class='wizard-followup-card'>", unsafe_allow_html=True)
            st.markdown(
                tr(
                    "Der Assistent hat Anschlussfragen, um fehlende Angaben zu ergänzen:",
                    "The assistant has generated follow-up questions to help fill in missing info:",
                )
            )
            st.markdown(
                tr(
                    "<p class='wizard-followup-meta'>Antworten werden automatisch gespeichert und im Profil gespiegelt.</p>",
                    "<p class='wizard-followup-meta'>Answers are saved automatically and synced with the profile.</p>",
                ),
                unsafe_allow_html=True,
            )
            if st.session_state.get(StateKeys.RAG_CONTEXT_SKIPPED):
                st.caption(
                    tr(
                        "Kontextvorschläge benötigen eine konfigurierte Vector-DB (VECTOR_STORE_ID).",
                        "Contextual suggestions require a configured vector store (VECTOR_STORE_ID).",
                    )
                )
            for q in list(followup_items):
                renderer(q, data)
            st.markdown("</div>", unsafe_allow_html=True)


def _render_followups_for_fields(
    fields: Iterable[str],
    data: dict,
    *,
    container: DeltaGenerator | None = None,
    container_factory: Callable[[], DeltaGenerator] | None = None,
) -> None:
    normalized_fields = tuple(str(field) for field in fields if field)
    if not normalized_fields:
        return
    _render_followups_for_section(
        normalized_fields,
        data,
        exact=True,
        container=container,
        container_factory=container_factory,
    )


def _render_followups_for_step(page_key: str, data: dict) -> None:
    prefixes = PAGE_FOLLOWUP_PREFIXES.get(page_key)
    if not prefixes:
        return
    _render_followups_for_section(prefixes, data)


def _apply_followup_updates(
    answers: Mapping[str, str],
    *,
    data: dict[str, Any],
    filtered_profile: Mapping[str, Any],
    profile_payload: Mapping[str, Any],
    target_value: str | None,
    manual_entries: Sequence[dict[str, str]],
    style_reference: str | None,
    lang: str,
    selected_fields: Collection[str],
    num_questions: int,
    warn_on_length: bool,
    show_feedback: bool,
    job_ad_generator: JobAdGenerator,
    interview_generator: InterviewGenerator,
) -> tuple[bool, bool]:
    for field_path, answer in answers.items():
        stripped = answer.strip()
        if stripped:
            set_in(data, field_path, stripped)

    job_generated = job_ad_generator(
        filtered_profile,
        selected_fields,
        target_value,
        manual_entries,
        style_reference,
        lang,
        show_feedback,
    )
    audience_choice = (
        st.session_state.get(StateKeys.INTERVIEW_AUDIENCE) or st.session_state.get(UIKeys.AUDIENCE_SELECT) or "general"
    )
    interview_generated = interview_generator(
        profile_payload,
        lang,
        num_questions,
        audience_choice,
        warn_on_length,
        show_feedback,
    )
    return job_generated, interview_generated


__all__ = [
    "CRITICAL_FIELD_PROMPTS",
    "DATE_FOLLOWUP_FIELDS",
    "INLINE_FOLLOWUP_FIELDS",
    "LIST_FOLLOWUP_FIELDS",
    "NUMBER_FOLLOWUP_FIELDS",
    "REQUIRED_PREFIX",
    "TargetedPromptConfig",
    "YES_NO_FOLLOWUP_FIELDS",
    "_apply_followup_updates",
    "_render_followups_for_fields",
    "_render_followups_for_section",
    "_render_followups_for_step",
]
