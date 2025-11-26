"""Interactive assistant for brainstorming role responsibilities."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

import config
from components.chatkit_widget import render_chatkit_widget
from constants.keys import StateKeys
from core.suggestions import get_responsibility_suggestions
from question_logic import tr
from wizard._logic import mark_ai_list_item
from utils.llm_state import llm_disabled_message


def _get_state() -> dict[str, Any]:
    state = st.session_state.setdefault(StateKeys.RESPONSIBILITY_BRAINSTORMER, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("messages", [])
    state.setdefault("last_title", None)
    state.setdefault("error", None)
    return state


def _store_state(state: Mapping[str, Any]) -> None:
    st.session_state[StateKeys.RESPONSIBILITY_BRAINSTORMER] = {
        "messages": list(state.get("messages", [])),
        "last_title": state.get("last_title"),
        "error": state.get("error"),
    }


def _append_unique(existing: Sequence[str], new_item: str) -> list[str]:
    seen = {entry.casefold() for entry in existing if isinstance(entry, str)}
    cleaned_new = new_item.strip()
    if not cleaned_new or cleaned_new.casefold() in seen:
        return list(existing)
    updated = list(existing)
    updated.append(cleaned_new)
    return updated


def _render_suggestions(
    *,
    message_index: int,
    suggestions: Sequence[str],
    responsibilities: Sequence[str],
    responsibilities_key: str,
    responsibilities_seed_key: str,
    lang: str,
) -> None:
    for suggestion_index, suggestion in enumerate(suggestions):
        suggestion_text = suggestion.strip()
        if not suggestion_text:
            continue
        add_key = f"{responsibilities_key}.chatkit.add.{message_index}.{suggestion_index}"
        dismiss_key = f"{responsibilities_key}.chatkit.dismiss.{message_index}.{suggestion_index}"
        cols = st.columns([0.76, 0.12, 0.12])
        cols[0].markdown(f"- {suggestion_text}")
        already_present = suggestion_text.casefold() in {item.casefold() for item in responsibilities}
        if already_present:
            cols[1].button(tr("Bereits erfasst", "Already added", lang=lang), key=f"{add_key}.disabled", disabled=True)
        elif cols[1].button(tr("Hinzufügen", "Add", lang=lang), key=add_key):
            updated_items = _append_unique(responsibilities, suggestion_text)
            st.session_state[StateKeys.RESPONSIBILITY_SUGGESTIONS] = {
                "_lang": lang,
                "items": [suggestion_text],
                "status": "applied",
            }
            st.session_state[responsibilities_key] = "\n".join(updated_items)
            st.session_state[responsibilities_seed_key] = "\n".join(updated_items)
            mark_ai_list_item(
                "responsibilities.items",
                suggestion_text,
                source="responsibility_brainstormer",
            )
            st.toast(
                tr("Aufgabe übernommen.", "Responsibility added.", lang=lang),
                icon="✅",
            )
            st.rerun()
        if cols[2].button(tr("Verwerfen", "Dismiss", lang=lang), key=dismiss_key):
            state = _get_state()
            messages = state.get("messages", [])
            if 0 <= message_index < len(messages):
                entry = dict(messages[message_index])
                remaining = [item for idx, item in enumerate(entry.get("suggestions", [])) if idx != suggestion_index]
                entry["suggestions"] = remaining
                messages[message_index] = entry
                state["messages"] = messages
                _store_state(state)
                st.rerun()


def _call_assistant(
    *,
    job_title: str,
    responsibilities: Sequence[str],
    company_name: str,
    team_structure: str,
    industry: str,
    tone_style: str | None,
    lang: str,
    focus_hints: Sequence[str] | None,
) -> None:
    suggestions, error = get_responsibility_suggestions(
        job_title,
        lang=lang,
        tone_style=tone_style,
        company_name=company_name,
        team_structure=team_structure,
        industry=industry,
        existing_items=responsibilities,
        focus_hints=focus_hints,
    )
    state = _get_state()
    state["error"] = error
    assistant_text = tr(
        "Hier sind Vorschläge – mit den Buttons kannst du sie übernehmen oder ausblenden.",
        "Here are suggestions – use the buttons to add or dismiss them.",
        lang=lang,
    )
    if error:
        assistant_text = tr(
            "Die KI konnte keine neuen Aufgaben liefern ({error}). Versuche es erneut oder passe den Fokus an.",
            "The assistant could not return responsibilities ({error}). Try again or adjust the focus.",
            lang=lang,
        ).format(error=error)
    elif not suggestions:
        assistant_text = tr(
            "Keine neuen Ideen gefunden. Gib mehr Kontext an, um konkretere Aufgaben zu erhalten.",
            "No new ideas yet. Provide more context to get sharper responsibilities.",
            lang=lang,
        )
    message: dict[str, Any] = {"role": "assistant", "content": assistant_text, "suggestions": suggestions}
    state.setdefault("messages", []).append(message)
    _store_state(state)


def render_responsibility_brainstormer(
    *,
    cleaned_responsibilities: Sequence[str],
    responsibilities_key: str,
    responsibilities_seed_key: str,
    job_title: str,
    company_name: str,
    team_structure: str,
    industry: str,
    tone_style: str | None,
    has_missing_key: bool,
) -> None:
    """Render the ChatKit responsibility brainstormer."""

    lang = st.session_state.get("lang", "de")
    state = _get_state()
    if state.get("last_title") != job_title:
        state = {"messages": [], "last_title": job_title, "error": None}
        _store_state(state)

    intro = tr(
        'Ich kann typische Aufgaben für diese Rolle vorschlagen. Klicke auf "Vorschläge abrufen" oder beschreibe den gewünschten Fokus – jede Idee lässt sich einzeln übernehmen.',
        'I can suggest common responsibilities for this role. Click "Fetch suggestions" or describe the focus you want — each idea can be added individually.',
        lang=lang,
    )
    if not state.get("messages"):
        state["messages"] = [{"role": "assistant", "content": intro, "suggestions": []}]
        _store_state(state)

    st.markdown("#### 🧠 " + tr("Aufgaben-Brainstormer (ChatKit)", "Responsibility brainstormer (ChatKit)", lang=lang))
    st.caption(
        tr(
            "Nutze die KI, um prägnante Verantwortlichkeiten vorzuschlagen und per Klick zu übernehmen.",
            "Use the assistant to brainstorm concise responsibilities and add them with one click.",
            lang=lang,
        )
    )

    if config.CHATKIT_RESPONSIBILITIES_WORKFLOW_ID:
        with st.expander(
            tr("💬 ChatKit-Widget (Rollenaufgaben)", "💬 ChatKit widget (responsibilities)", lang=lang),
            expanded=False,
        ):
            render_chatkit_widget(
                workflow_id=config.CHATKIT_RESPONSIBILITIES_WORKFLOW_ID,
                conversation_key="responsibility_brainstormer",
                title_md=tr(
                    "##### Live-Chat für Aufgabenideen",
                    "##### Live chat for responsibility ideas",
                    lang=lang,
                ),
                description=tr(
                    "Nutze den eingebetteten ChatKit-Assistenten, um Aufgaben vorzuschlagen, die zum Rollenfokus passen.",
                    "Use the embedded ChatKit assistant to suggest responsibilities tailored to this role.",
                    lang=lang,
                ),
                lang=lang,
                height=520,
            )
        st.write("---")

    disabled_reasons: list[str] = []
    if has_missing_key:
        disabled_reasons.append(llm_disabled_message(lang=lang))
    if not job_title:
        disabled_reasons.append(
            tr(
                "Bitte trage einen Jobtitel ein, um passende Aufgaben zu erhalten.",
                "Enter a job title to generate tailored responsibilities.",
                lang=lang,
            )
        )
    if not config.CHATKIT_ENABLED:
        disabled_reasons.append(
            tr(
                "ChatKit ist deaktiviert – aktiviere CHATKIT_ENABLED für Live-Vorschläge.",
                "ChatKit is disabled — enable CHATKIT_ENABLED for live suggestions.",
                lang=lang,
            )
        )

    for reason in disabled_reasons:
        st.caption(reason)

    chat_container = st.container()
    with chat_container:
        for index, message in enumerate(state.get("messages", [])):
            content = str(message.get("content") or "").strip()
            role = str(message.get("role") or "assistant")
            suggestions = message.get("suggestions") or []
            if not content and not suggestions:
                continue
            with st.chat_message(role):
                if content:
                    st.markdown(content)
                if suggestions:
                    _render_suggestions(
                        message_index=index,
                        suggestions=suggestions,
                        responsibilities=cleaned_responsibilities,
                        responsibilities_key=responsibilities_key,
                        responsibilities_seed_key=responsibilities_seed_key,
                        lang=lang,
                    )

    button_label = "💡 " + tr("Vorschläge abrufen", "Fetch suggestions", lang=lang)
    if st.button(button_label, disabled=bool(disabled_reasons)):
        _call_assistant(
            job_title=job_title,
            responsibilities=cleaned_responsibilities,
            company_name=company_name,
            team_structure=team_structure,
            industry=industry,
            tone_style=tone_style,
            lang=lang,
            focus_hints=[],
        )
        st.rerun()

    prompt = st.chat_input(
        tr(
            "Fokus oder Kontext eingeben (z. B. Stakeholder-Management, Roadmap, Budget)…",
            "Share a focus or context (e.g., stakeholder management, roadmap, budget)…",
            lang=lang,
        ),
        key=f"chatkit.responsibilities.input.{lang}",
        disabled=bool(disabled_reasons),
    )
    if prompt is not None:
        normalized_prompt = prompt.strip()
        if normalized_prompt:
            state = _get_state()
            state.setdefault("messages", []).append({"role": "user", "content": normalized_prompt})
            _store_state(state)
            _call_assistant(
                job_title=job_title,
                responsibilities=cleaned_responsibilities,
                company_name=company_name,
                team_structure=team_structure,
                industry=industry,
                tone_style=tone_style,
                lang=lang,
                focus_hints=[normalized_prompt],
            )
            st.rerun()
        else:
            st.toast(
                tr(
                    "Bitte Kontext eingeben, um neue Ideen zu erhalten.",
                    "Please share some context to get fresh ideas.",
                    lang=lang,
                ),
                icon="ℹ️",
            )

    state = _get_state()
    if state.get("error") and not disabled_reasons:
        st.info(state["error"])
