"""Interactive assistant for brainstorming role responsibilities."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

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


def _collect_suggestions(
    *,
    state: Mapping[str, Any],
    responsibilities: Iterable[str],
) -> list[tuple[str, int, str]]:
    existing = {item.casefold() for item in responsibilities if isinstance(item, str)}
    collected: list[tuple[str, int, str]] = []
    for message_index, message in enumerate(state.get("messages", [])):
        for suggestion_index, suggestion in enumerate(message.get("suggestions") or []):
            suggestion_text = str(suggestion or "").strip()
            if not suggestion_text:
                continue
            if suggestion_text.casefold() in existing:
                continue
            collected.append((f"{message_index}:{suggestion_index}", message_index, suggestion_text))
    return collected


def _render_suggestion_panel(
    *,
    state: Mapping[str, Any],
    suggestions: list[tuple[str, int, str]],
    responsibilities_key: str,
    responsibilities_seed_key: str,
    lang: str,
    disabled: bool,
) -> None:
    selection_key = f"{responsibilities_key}.chatkit.selection"
    suggested_state_key = f"{responsibilities_key}.__suggested"
    st.session_state.setdefault(selection_key, [])
    selected_ids = {str(item) for item in st.session_state.get(selection_key, [])}
    current_value = st.session_state.get(responsibilities_key, "")
    current_items = [item.strip() for item in current_value.split("\n") if item.strip()]
    merged_items = list(dict.fromkeys(current_items))

    st.sidebar.markdown(
        "#### "
        + tr(
            "Vorschlags-Palette",
            "Suggestion palette",
            lang=lang,
        )
    )
    st.sidebar.caption(
        tr(
            "Markiere Aufgaben und übernimm sie gesammelt per Klick.",
            "Select responsibilities and apply them in bulk.",
            lang=lang,
        )
    )

    if not suggestions:
        st.sidebar.info(
            tr(
                "Noch keine neuen Vorschläge – fordere Ideen im Chat an.",
                "No new suggestions yet — request ideas via the chat.",
                lang=lang,
            )
        )
        return

    available_ids = {item_id for item_id, _, _ in suggestions}
    selected_ids = selected_ids.intersection(available_ids)

    for item_id, message_index, suggestion_text in suggestions:
        checkbox_key = f"{selection_key}.{item_id}"
        is_selected = item_id in selected_ids
        updated_selected = st.sidebar.checkbox(
            suggestion_text,
            key=checkbox_key,
            value=is_selected,
            disabled=disabled,
        )
        if updated_selected:
            selected_ids.add(item_id)
        else:
            selected_ids.discard(item_id)

    st.session_state[selection_key] = sorted(selected_ids)

    def _clear_from_state(ids_to_clear: set[str]) -> None:
        if not ids_to_clear:
            return
        messages = list(state.get("messages", []))
        for item_id in ids_to_clear:
            if ":" not in item_id:
                continue
            message_index_str, suggestion_index_str = item_id.split(":", maxsplit=1)
            try:
                message_index_int = int(message_index_str)
                suggestion_index_int = int(suggestion_index_str)
            except ValueError:
                continue
            if 0 <= message_index_int < len(messages):
                entry = dict(messages[message_index_int])
                remaining = [
                    item for idx, item in enumerate(entry.get("suggestions", [])) if idx != suggestion_index_int
                ]
                entry["suggestions"] = remaining
                messages[message_index_int] = entry
        updated_state = dict(state)
        updated_state["messages"] = messages
        _store_state(updated_state)

    def _apply_selected(ids_to_apply: set[str]) -> None:
        if not ids_to_apply:
            st.toast(
                tr(
                    "Bitte mindestens einen Vorschlag auswählen.",
                    "Select at least one suggestion first.",
                    lang=lang,
                ),
                icon="ℹ️",
            )
            return
        additions: list[str] = []
        for item_id, _, suggestion_text in suggestions:
            if item_id not in ids_to_apply:
                continue
            merged_items[:] = _append_unique(merged_items, suggestion_text)
            additions.append(suggestion_text)
        if not additions:
            st.toast(
                tr("Keine neuen Aufgaben hinzugefügt.", "No new responsibilities added.", lang=lang),
                icon="ℹ️",
            )
            return
        updated_text = "\n".join(merged_items)
        st.session_state[responsibilities_key] = updated_text
        st.session_state[responsibilities_seed_key] = updated_text
        st.session_state[suggested_state_key] = updated_text
        st.session_state[StateKeys.RESPONSIBILITY_SUGGESTIONS] = {
            "_lang": lang,
            "items": additions,
            "status": "applied",
        }
        for item in additions:
            mark_ai_list_item(
                "responsibilities.items",
                item,
                source="responsibility_brainstormer",
            )
        _clear_from_state(ids_to_apply)
        st.session_state[selection_key] = []
        st.toast(
            tr(
                "Vorschläge übernommen.",
                "Suggestions applied.",
                lang=lang,
            ),
            icon="✅",
        )
        st.rerun()

    def _reject_all() -> None:
        _clear_from_state(available_ids)
        st.session_state[selection_key] = []
        st.toast(
            tr("Alle Vorschläge verworfen.", "All suggestions dismissed.", lang=lang),
            icon="🗑️",
        )
        st.rerun()

    st.sidebar.divider()
    apply_all_clicked = st.sidebar.button(
        "✅ " + tr("Alle übernehmen", "Apply all", lang=lang),
        disabled=disabled or not suggestions,
    )
    apply_selected_clicked = st.sidebar.button(
        "📥 " + tr("Auswahl übernehmen", "Apply selection", lang=lang),
        disabled=disabled or not suggestions,
    )
    reject_all_clicked = st.sidebar.button(
        "🗑️ " + tr("Alle verwerfen", "Dismiss all", lang=lang),
        disabled=disabled or not suggestions,
    )

    if apply_all_clicked:
        _apply_selected(available_ids)
    elif apply_selected_clicked:
        _apply_selected(selected_ids)
    elif reject_all_clicked:
        _reject_all()


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
        "Hier sind Vorschläge – nutze die Checkboxen im Seitenpanel, um sie gesammelt zu prüfen.",
        "Here are suggestions — review them via the side panel checkboxes.",
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
    if responsibilities_key not in st.session_state:
        st.session_state[responsibilities_key] = "\n".join(
            item.strip() for item in cleaned_responsibilities if item.strip()
        )
        st.session_state[responsibilities_seed_key] = st.session_state[responsibilities_key]

    current_value = st.session_state.get(
        responsibilities_key,
        "\n".join(item.strip() for item in cleaned_responsibilities if item.strip()),
    )
    responsibility_items = [item.strip() for item in current_value.split("\n") if item.strip()]

    state = _get_state()
    if state.get("last_title") != job_title:
        state = {"messages": [], "last_title": job_title, "error": None}
        _store_state(state)

    intro = tr(
        'Ich kann typische Aufgaben für diese Rolle vorschlagen. Klicke auf "Vorschläge abrufen" oder beschreibe den gewünschten Fokus – neue Ideen landen gesammelt im Seitenpanel.',
        'I can suggest common responsibilities for this role. Click "Fetch suggestions" or describe the focus you want — new ideas collect in the side panel.',
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

    suggestions_for_panel = _collect_suggestions(
        state=state,
        responsibilities=responsibility_items,
    )
    _render_suggestion_panel(
        state=state,
        suggestions=suggestions_for_panel,
        responsibilities_key=responsibilities_key,
        responsibilities_seed_key=responsibilities_seed_key,
        lang=lang,
        disabled=bool(disabled_reasons),
    )

    chat_container = st.container()
    with chat_container:
        for message in state.get("messages", []):
            content = str(message.get("content") or "").strip()
            role = str(message.get("role") or "assistant")
            suggestions = message.get("suggestions") or []
            if not content and not suggestions:
                continue
            with st.chat_message(role):
                if content:
                    st.markdown(content)
                if suggestions:
                    st.caption(
                        tr(
                            "Vorschläge sind im Seitenpanel auswählbar.",
                            "Suggestions are selectable in the side panel.",
                            lang=lang,
                        )
                    )

    button_label = "💡 " + tr("Vorschläge abrufen", "Fetch suggestions", lang=lang)
    if st.button(button_label, disabled=bool(disabled_reasons)):
        _call_assistant(
            job_title=job_title,
            responsibilities=responsibility_items,
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
                responsibilities=responsibility_items,
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
