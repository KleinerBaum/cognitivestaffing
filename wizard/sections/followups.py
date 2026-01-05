"""Rendering and utility helpers for follow-up questions."""

from __future__ import annotations

import html
import logging
import sys
from datetime import date
from typing import (
    Any,
    Callable,
    Collection,
    Final,
    Iterable,
    Literal,
    Mapping,
    Sequence,
    TypedDict,
)

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import config
from components.chatkit_widget import render_chatkit_widget
from constants.keys import ProfilePaths, StateKeys, UIKeys
from utils.i18n import tr
from wizard.followups import followup_has_response
from wizard.metadata import FIELD_SECTION_MAP, PAGE_FOLLOWUP_PREFIXES, get_missing_critical_fields
from wizard.types import LangPair, LangSuggestionPair
from wizard._logic import _get_profile_state, _sync_followup_completion, get_in, set_in, _update_profile
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
FOLLOWUP_FOCUS_BUDGET_KEY: Final[str] = "_followup_focus_consumed"
CHATKIT_STATE_KEY: Final[str] = "wizard.chatkit.followups"
logger = logging.getLogger(__name__)

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


def _render_followup_notice(source: str, reason: str, *, lang: str) -> None:
    if not source or source == "llm":
        return

    if source == "fallback":
        detail = tr(
            "Automatische Anschlussfragen waren nicht verfügbar. Wir zeigen Standardfragen an.",
            "Automatic follow-ups were unavailable. Showing default prompts instead.",
            lang=lang,
        )
        if reason == "empty_result":
            detail = tr(
                "Die KI lieferte keine Anschlussfragen – Standardfragen werden angezeigt.",
                "The AI returned no follow-up questions – displaying default prompts instead.",
                lang=lang,
            )
        st.info(detail)
        return

    if source == "error":
        st.warning(
            tr(
                "Konnte keine Anschlussfragen generieren – bitte fehlende Felder manuell ergänzen.",
                "Unable to generate follow-up questions – please fill missing fields manually.",
                lang=lang,
            )
        )


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
    """Normalize follow-up inputs into a trimmed list of strings."""

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    return []


def _ensure_followup_styles() -> None:
    """Inject CSS for follow-up cards once per session."""

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
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.3));
                border-left: 5px solid var(--border-subtle, rgba(59, 130, 246, 0.45));
                opacity: 0;
                transition: border-color var(--transition-base, 0.18s ease-out),
                    box-shadow var(--transition-base, 0.18s ease-out),
                    transform var(--transition-base, 0.18s ease-out);
                animation: wizardFollowupIn 0.5s ease forwards;
            }

            .wizard-followup-item.is-critical {
                background: linear-gradient(
                    135deg,
                    rgba(254, 242, 242, 0.85) 0%,
                    rgba(255, 255, 255, 0.95) 80%
                );
                border-left-color: rgba(220, 38, 38, 0.65);
                border-color: rgba(248, 113, 113, 0.4);
            }

            .wizard-followup-item:hover,
            .wizard-followup-item:focus-within {
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
                transform: translateY(-1px);
            }

            .wizard-followup-question {
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                font-weight: 640;
                color: var(--text-strong, #0f172a);
                margin-bottom: 0.25rem;
            }

            .wizard-followup-question .wizard-followup-icon {
                width: 1.35rem;
                height: 1.35rem;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                font-size: 0.88rem;
                background: rgba(59, 130, 246, 0.12);
                color: rgba(30, 64, 175, 0.92);
                border: 1px solid rgba(59, 130, 246, 0.35);
            }

            .wizard-followup-question.is-critical .wizard-followup-icon {
                background: rgba(248, 113, 113, 0.14);
                color: rgba(185, 28, 28, 0.96);
                border-color: rgba(248, 113, 113, 0.55);
            }

            .wizard-followup-question.is-critical {
                color: rgba(153, 27, 27, 0.98);
            }

            .wizard-followup-required {
                color: rgba(220, 38, 38, 0.95);
                font-weight: 700;
            }

            .wizard-followup-meta {
                color: rgba(15, 23, 42, 0.6);
                font-size: 0.85rem;
            }

            .wizard-followup-description {
                color: var(--text-soft, rgba(15, 23, 42, 0.62));
                font-size: 0.92rem;
                font-style: italic;
                margin-bottom: 0.25rem;
                display: inline-flex;
                gap: 0.35rem;
                align-items: center;
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
    """Apply a suggested answer with type-aware coercion for the target field."""

    normalized = suggestion.strip()
    if not normalized:
        return
    processed_value: Any = normalized
    if field in YES_NO_FOLLOWUP_FIELDS:
        lowered = normalized.casefold()
        st.session_state[key] = lowered in {"yes", "ja", "true", "wahr", "1", "y"}
        st.session_state[f"{key}_touched"] = True
        processed_value = bool(st.session_state[key])
    elif field in DATE_FOLLOWUP_FIELDS:
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError:
            parsed = None
        st.session_state[key] = parsed if parsed is not None else normalized
        processed_value = parsed.isoformat() if isinstance(parsed, date) else normalized
    elif field in NUMBER_FOLLOWUP_FIELDS:
        cleaned = normalized.replace(",", ".")
        try:
            st.session_state[key] = int(float(cleaned))
        except ValueError:
            st.session_state[key] = normalized
        processed_value = st.session_state[key]
    elif field in LIST_FOLLOWUP_FIELDS:
        current = str(st.session_state.get(key, "") or "")
        items = [line.strip() for line in current.splitlines() if line.strip()]
        if normalized not in items:
            items.append(normalized)
        st.session_state[key] = "\n".join(items)
        processed_value = [line for line in items if line]
    st.session_state[key] = st.session_state.get(key, normalized) or normalized
    inline_field = field in INLINE_FOLLOWUP_FIELDS
    should_sync_widget_state = not inline_field
    _update_profile(field, processed_value, session_value=processed_value, sync_widget_state=should_sync_widget_state)


def _coerce_followup_number(value: Any) -> int:
    """Convert incoming number-like follow-up values to integers."""

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
    """Return the language tuple index for German/English pairs."""

    if not lang:
        return 0
    return 0 if lang.lower().startswith("de") else 1


def _select_lang_text(pair: LangPair | None, lang: str | None) -> str:
    """Pick the localized text for the active language."""

    if not pair:
        return ""
    idx = _lang_index(lang)
    return pair[idx] if idx < len(pair) else pair[0]


def _select_lang_suggestions(pair: LangSuggestionPair | None, lang: str | None) -> list[str]:
    """Pick the localized suggestions list for the active language."""

    if not pair:
        return []
    idx = _lang_index(lang)
    if idx >= len(pair):
        idx = 0
    return list(pair[idx])


def _ensure_targeted_followup(field: str) -> None:
    """Create a targeted follow-up question for a missing critical field."""

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
    """Return missing fields for the section and enqueue targeted follow-ups."""

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


def _humanize_followup_label(path: str, lang: str) -> str:
    """Return a readable label for a follow-up field path."""

    cleaned = path.replace("_", " ").replace(".", " ").strip()
    readable = " ".join(part.capitalize() for part in cleaned.split()) or path
    return tr(readable, readable, lang=lang)


def _chatkit_enabled() -> bool:
    """Return ``True`` when the ChatKit assistant should be rendered."""

    return bool(config.CHATKIT_ENABLED)


def _get_chat_state(section_key: str) -> dict[str, Any]:
    """Return the persisted chat state for ``section_key``."""

    base_state = st.session_state.setdefault(CHATKIT_STATE_KEY, {})
    state = base_state.get(section_key)
    if not isinstance(state, dict):
        state = {"messages": [], "pending": [], "current_field": None}
        base_state[section_key] = state
    if "messages" not in state:
        state["messages"] = []
    if "pending" not in state:
        state["pending"] = []
    if "current_field" not in state:
        state["current_field"] = None
    return state


def _store_chat_state(section_key: str, state: Mapping[str, Any]) -> None:
    """Persist chat state back into session."""

    base_state = st.session_state.setdefault(CHATKIT_STATE_KEY, {})
    base_state[section_key] = {
        "messages": list(state.get("messages", [])),
        "pending": list(state.get("pending", [])),
        "current_field": state.get("current_field"),
    }
    st.session_state[CHATKIT_STATE_KEY] = base_state


def _build_question_text(question: Mapping[str, Any], lang: str) -> str:
    """Return a localized question including optional suggestions."""

    prompt = str(question.get("question") or "").strip()
    description = str(question.get("description") or "").strip()
    suggestions = question.get("suggestions") or []
    suggestion_lines = [str(item).strip() for item in suggestions if str(item).strip()]
    segments = [prompt or tr("Welche Information fehlt?", "Which detail is missing?", lang=lang)]
    if description:
        segments.append(description)
    if suggestion_lines:
        bullet_prefix = tr("Vorschläge:", "Suggestions:", lang=lang)
        formatted = "\n".join(f"- {line}" for line in suggestion_lines)
        segments.append(f"{bullet_prefix}\n{formatted}")
    return "\n\n".join(segment for segment in segments if segment)


def _render_chatkit_followup_assistant(
    *,
    followup_items: Sequence[Mapping[str, Any]],
    data: dict,
    step_label: str | None,
    section_key: str,
) -> None:
    """Render the interactive ChatKit assistant for missing fields."""

    if not _chatkit_enabled():
        return

    lang = st.session_state.get("lang", "de")
    chatkit_workflow = config.CHATKIT_FOLLOWUPS_WORKFLOW_ID
    if config.CHATKIT_DOMAIN_KEY and chatkit_workflow:
        render_chatkit_widget(
            workflow_id=chatkit_workflow,
            conversation_key=f"followups.{section_key}",
            title_md=tr(
                "### 🧠 ChatKit-Assistent für fehlende Angaben",
                "### 🧠 ChatKit assistant for missing info",
                lang=lang,
            ),
            description=tr(
                "Der eingebettete ChatKit-Flow ist für diese Domain freigeschaltet und kann Pflichtfelder einsammeln.",
                "The embedded ChatKit flow is allow-listed for this domain and can capture required fields.",
                lang=lang,
            ),
            lang=lang,
            height=580,
        )
        return
    state = _get_chat_state(section_key)
    pending_fields = [str(item.get("field", "")) for item in followup_items if item.get("field")]
    pending_fields = [field for field in pending_fields if field]
    if not pending_fields:
        _store_chat_state(section_key, state)
        return

    state_pending = [field for field in state.get("pending", []) if field in pending_fields]
    for field in pending_fields:
        if field not in state_pending:
            state_pending.append(field)
    state["pending"] = state_pending
    question_lookup = {str(item.get("field")): item for item in followup_items if item.get("field")}

    if not state.get("messages"):
        intro = tr(
            "Ich helfe, die fehlenden Pflichtfelder Schritt für Schritt zu ergänzen.",
            "I’ll help capture the missing required fields step by step.",
            lang=lang,
        )
        if step_label:
            intro = f"{intro}\n\n{tr('Abschnitt:', 'Section:', lang=lang)} {step_label}"
        state["messages"] = [
            {"role": "assistant", "content": intro, "field": None},
        ]

    current_field = state.get("current_field")
    if current_field not in state_pending:
        current_field = state_pending[0] if state_pending else None
    if current_field and not any(
        message.get("role") == "assistant" and message.get("field") == current_field
        for message in state.get("messages", [])
    ):
        question_text = _build_question_text(question_lookup.get(current_field, {}), lang)
        state.setdefault("messages", []).append({"role": "assistant", "content": question_text, "field": current_field})

    with st.container():
        st.markdown(
            tr(
                "### 🧠 ChatKit-Assistent für fehlende Angaben",
                "### 🧠 ChatKit assistant for missing info",
                lang=lang,
            )
        )
        if config.CHATKIT_DOMAIN_KEY or config.CHATKIT_WORKFLOW_ID:
            st.caption(
                tr(
                    "ChatKit ist eingebunden und darf auf dieser Domain antworten.",
                    "ChatKit is embedded and authorized for this domain.",
                    lang=lang,
                )
            )
        else:
            st.caption(
                tr(
                    "Lokaler Fallback aktiv – Antworten werden trotzdem live übernommen.",
                    "Local fallback is active — answers are still applied live.",
                    lang=lang,
                )
            )

        for message in state.get("messages", []):
            role = str(message.get("role") or "assistant")
            content = str(message.get("content") or "")
            if not content.strip():
                continue
            st.chat_message(role).markdown(content)

        input_key = f"chatkit.input.{section_key}"
        prompt = st.chat_input(
            tr("Antwort eingeben …", "Share your answer …", lang=lang),
            key=input_key,
            disabled=not current_field,
        )

        if prompt is not None:
            normalized_prompt = prompt.strip()
            if not normalized_prompt:
                st.toast(
                    tr(
                        "Bitte gib eine kurze Antwort ein, damit ich das Feld ausfüllen kann.",
                        "Please provide an answer so I can fill the field.",
                        lang=lang,
                    ),
                )
            else:
                state.setdefault("messages", []).append(
                    {"role": "user", "content": normalized_prompt, "field": current_field}
                )
                if current_field:
                    _update_profile(current_field, normalized_prompt)
                    try:
                        set_in(data, current_field, normalized_prompt)
                    except Exception:
                        logger.debug("Unable to mirror ChatKit update into local data map", exc_info=True)
                    label = _humanize_followup_label(current_field, lang)
                    ack = tr(
                        "Verstanden – ich habe {label} aktualisiert.",
                        "Got it — I’ve updated {label}.",
                        lang=lang,
                    ).format(label=label)
                    state["messages"].append({"role": "assistant", "content": ack, "field": current_field})
                    state_pending = [field for field in state_pending if field != current_field]
                    state["pending"] = state_pending
                    if state_pending:
                        next_field = state_pending[0]
                        state["current_field"] = next_field
                        next_question = _build_question_text(
                            question_lookup.get(next_field, {}),
                            lang,
                        )
                        state["messages"].append(
                            {
                                "role": "assistant",
                                "content": next_question,
                                "field": next_field,
                            }
                        )
                    else:
                        state["current_field"] = None
                        state["messages"].append(
                            {
                                "role": "assistant",
                                "content": tr(
                                    "Alle Pflichtfelder in diesem Schritt sind nun ausgefüllt. Danke!",
                                    "All required fields for this step are now filled. Thank you!",
                                    lang=lang,
                                ),
                                "field": None,
                            }
                        )
                else:
                    state["messages"].append(
                        {
                            "role": "assistant",
                            "content": tr("Danke für die Rückmeldung!", "Thanks for the update!", lang=lang),
                            "field": None,
                        }
                    )

    _store_chat_state(section_key, state)


def _normalize_list_value(existing_value: Any) -> str:
    """Flatten stored list data into the textarea-friendly format."""

    return "\n".join(_normalize_followup_list(existing_value))


def _default_date(existing_value: Any) -> date:
    """Return a safe default date for follow-up date inputs."""

    return default_date(existing_value)


def _should_render_for_field(field: str, prefixes: Sequence[str], exact: bool) -> bool:
    """Check whether a follow-up question should display for the given prefixes."""

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


def _resolve_step_label(page_key: str) -> str:
    """Return an English label for the current step for logging purposes."""

    flow_module = sys.modules.get("wizard.flow")
    page_lookup = getattr(flow_module, "PAGE_LOOKUP", {}) if flow_module else {}
    label = page_key
    if isinstance(page_lookup, Mapping):
        page = page_lookup.get(page_key)
        if page is not None:
            try:
                header_en = page.header_for("en")
            except Exception:  # pragma: no cover - defensive guard
                header_en = ""
            if isinstance(header_en, str) and header_en.strip():
                label = header_en.strip()
    return label


def _render_followup_question(q: dict, data: dict) -> None:
    """Render a single follow-up question and sync its answer to the profile."""

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
    toast_sentinel = f"{key}_toast_shown"
    container = st.container()
    priority = q.get("priority")
    priority_class = "is-critical" if priority == "critical" else "is-standard"
    with container:
        st.markdown(f"<div id='{anchor}'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='wizard-followup-item {priority_class}'>",
            unsafe_allow_html=True,
        )
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
        focus_available = not st.session_state.get(FOLLOWUP_FOCUS_BUDGET_KEY, False)
        st.session_state[focus_sentinel] = focus_available
        if focus_available:
            st.session_state[FOLLOWUP_FOCUS_BUDGET_KEY] = True
    if highlight_sentinel not in st.session_state:
        st.session_state[highlight_sentinel] = True
    if toast_sentinel not in st.session_state:
        st.session_state[toast_sentinel] = False
    ui_variant = q.get("ui_variant")
    description = q.get("description")
    if not description:
        missing_fields = st.session_state.get(StateKeys.EXTRACTION_MISSING) or []
        if field in missing_fields:
            description = tr(
                "Diese Angabe fehlte in der Stellenanzeige.",
                "This detail was not found in the job ad.",
            )
    if ui_variant in ("info", "warning") and description:
        getattr(container, ui_variant)(description)
    elif description:
        container.markdown(
            f"<div class='wizard-followup-description'>🛈 {description}</div>",
            unsafe_allow_html=True,
        )
    question_text = prompt or tr("Antwort eingeben", "Enter response")
    required_badge = "<span class='wizard-followup-required'>*</span>" if priority == "critical" else ""
    display_question = html.escape(question_text)
    icon = "⚠️" if priority == "critical" else "🛈"
    question_markup = (
        "<div class='wizard-followup-question {cls}'>"
        "<span class='wizard-followup-icon'>{icon}</span>"
        "{required}{text}"
        "</div>"
    ).format(cls=priority_class, icon=icon, required=required_badge, text=display_question)
    with container:
        st.markdown(question_markup, unsafe_allow_html=True)
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
    label_text = f"* {question_text}" if priority == "critical" else question_text
    processed_value: Any
    touched_key: str | None = None
    with container:
        if field in YES_NO_FOLLOWUP_FIELDS:
            touched_key = f"{key}_touched"
            if touched_key not in st.session_state:
                st.session_state[touched_key] = existing_value is not None

            def _mark_followup_touched() -> None:
                """Mark checkbox-driven follow-ups as interacted with."""

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
            should_toast = priority == "critical" and not st.session_state.get(toast_sentinel, False)
            if should_toast:
                st.toast(
                    tr("Neue kritische Anschlussfrage", "New critical follow-up"),
                    icon="⚠️",
                )
                st.session_state[toast_sentinel] = True
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
    inline_field = field in INLINE_FOLLOWUP_FIELDS
    should_sync_widget_state = not inline_field
    # Keep follow-up values flowing through widget return values; mutating
    # canonical session_state keys after mount triggers Streamlit immutable-key
    # errors and desynchronises sidebar badges.
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
        st.session_state.pop(toast_sentinel, None)
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
    step_label: str | None = None,
) -> None:
    """Render follow-ups for fields matching the provided prefixes."""

    normalized_prefixes = tuple(str(prefix) for prefix in prefixes if prefix)
    if not normalized_prefixes:
        return

    lang = st.session_state.get("lang", "de")
    notice_source = str(st.session_state.get(StateKeys.FOLLOWUPS_SOURCE) or "")
    notice_reason = str(st.session_state.get(StateKeys.FOLLOWUPS_REASON) or "")
    _render_followup_notice(notice_source, notice_reason, lang=lang)

    profile_data = _get_profile_state()
    st.session_state[FOLLOWUP_FOCUS_BUDGET_KEY] = False
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
        profile_value = get_in(profile_data, field, None)
        if followup_has_response(profile_value):
            _sync_followup_completion(field, profile_value, profile_data)
            continue
        followup_items.append(question)

    if followup_items:
        renderer = _resolve_followup_renderer()
        _ensure_followup_styles()
        target_container = container
        if target_container is None:
            target_container = container_factory() if container_factory else st.container()

        chat_section_key = step_label or "|".join(normalized_prefixes)
        chat_enabled = _chatkit_enabled()
        if chat_enabled:
            _render_chatkit_followup_assistant(
                followup_items=followup_items,
                data=data,
                step_label=step_label,
                section_key=chat_section_key,
            )
            target_container = target_container.expander(
                tr(
                    "Manuelle Eingabe anzeigen",
                    "Show manual capture",
                ),
                expanded=False,
            )

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
                try:
                    renderer(q, data)
                except Exception:  # pragma: no cover - defensive guard
                    step_name = step_label or "follow-up section"
                    field = str(q.get("field", "")).strip() or "unknown field"
                    logger.exception(
                        "⚠️ Error rendering follow-ups for step '%s' (field '%s'); skipping remaining follow-up questions.",
                        step_name,
                        field,
                    )
                    break
            st.markdown("</div>", unsafe_allow_html=True)


def _render_followups_for_fields(
    fields: Iterable[str],
    data: dict,
    *,
    container: DeltaGenerator | None = None,
    container_factory: Callable[[], DeltaGenerator] | None = None,
) -> None:
    """Render follow-ups for an explicit list of fields."""

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
    """Render follow-ups for the given wizard page key."""

    prefixes = PAGE_FOLLOWUP_PREFIXES.get(page_key)
    if not prefixes:
        return
    _render_followups_for_section(prefixes, data, step_label=_resolve_step_label(page_key))


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
    """Persist follow-up answers and trigger downstream generation calls."""

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
