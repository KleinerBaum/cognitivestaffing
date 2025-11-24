"""UI wrapper for the team composition advisor ChatKit."""

from __future__ import annotations

import logging
from typing import Any, Callable, Mapping

import streamlit as st

from constants.keys import ProfilePaths
from llm.team_advisor import TeamAdvice, advise_team_structure
from utils.i18n import tr

logger = logging.getLogger(__name__)

_TEAM_ADVISOR_STATE_KEY = "wizard.team_advisor.chat"


def _get_state() -> dict[str, Any]:
    state = st.session_state.setdefault(_TEAM_ADVISOR_STATE_KEY, {})
    state.setdefault("messages", [])
    state.setdefault("started", False)
    state.setdefault("pending_suggestion", {})
    return state


def _append_message(state: dict[str, Any], role: str, content: str) -> None:
    if not content.strip():
        return
    state.setdefault("messages", []).append({"role": role, "content": content})


def _acknowledge_update(message: str, lang: str) -> None:
    st.toast(message)
    logger.debug("Team advisor applied update: %s", message)


def _apply_reports_to(
    value: str,
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
    lang: str,
) -> None:
    reporting_line = value.strip()
    position["reports_to"] = reporting_line
    update_profile(ProfilePaths.POSITION_REPORTS_TO, reporting_line)
    _acknowledge_update(
        tr("Berichtslinie übernommen.", "Reporting line applied.", lang=lang),
        lang,
    )


def _apply_direct_reports(
    count: int,
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
    lang: str,
) -> None:
    normalized = max(int(count), 0)
    position["supervises"] = normalized
    update_profile(ProfilePaths.POSITION_SUPERVISES, normalized)
    _acknowledge_update(
        tr("Anzahl direkter Reports gesetzt.", "Direct reports updated.", lang=lang),
        lang,
    )


def _render_suggestion_actions(
    advice: TeamAdvice,
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
    lang: str,
) -> None:
    suggestions_available = any((advice.reporting_line, advice.direct_reports is not None))
    if not suggestions_available:
        return

    st.write("---")
    st.caption(tr("KI-Vorschläge anwenden", "Apply AI suggestions", lang=lang))
    cols = st.columns(2)
    if advice.reporting_line:
        if cols[0].button(
            tr(
                f"Berichtet an setzen: {advice.reporting_line}",
                f"Set reports to: {advice.reporting_line}",
                lang=lang,
            ),
            key="team_advisor.apply_reporting_line",
        ):
            _apply_reports_to(advice.reporting_line, position, update_profile, lang)

    if advice.direct_reports is not None:
        direct_label = tr(
            f"Direkte Reports setzen: {advice.direct_reports}",
            f"Set direct reports: {advice.direct_reports}",
            lang=lang,
        )
        if cols[1].button(direct_label, key="team_advisor.apply_direct_reports"):
            _apply_direct_reports(advice.direct_reports, position, update_profile, lang)


def _render_chat_messages(state: dict[str, Any]) -> None:
    for message in state.get("messages", []):
        role = str(message.get("role") or "assistant")
        content = str(message.get("content") or "")
        if not content.strip():
            continue
        st.chat_message(role).markdown(content)


def _record_advice(
    advice: TeamAdvice,
    state: dict[str, Any],
    *,
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
    lang: str,
) -> None:
    body = advice.message
    if advice.follow_up_question:
        body = f"{body}\n\n{tr('Rückfrage', 'Follow-up question', lang=lang)}: {advice.follow_up_question}"
    _append_message(state, "assistant", body)
    state["pending_suggestion"] = {
        "reporting_line": advice.reporting_line,
        "direct_reports": advice.direct_reports,
    }


def _render_pending_actions(
    state: Mapping[str, Any],
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
    lang: str,
) -> None:
    pending = state.get("pending_suggestion") or {}
    advice = TeamAdvice(
        message="",
        reporting_line=pending.get("reporting_line"),
        direct_reports=pending.get("direct_reports"),
    )
    _render_suggestion_actions(advice, position, update_profile, lang)


def render_team_advisor(
    *,
    profile: Mapping[str, Any],
    position: dict[str, Any],
    update_profile: Callable[[str, Any], None],
) -> None:
    """Render the team composition advisor inside the Team step."""

    state = _get_state()
    lang = st.session_state.get("lang", "de")

    with st.expander(
        tr("🧠 Team-Kompositions-Assistent", "🧠 Team composition advisor", lang=lang),
        expanded=False,
    ):
        st.caption(
            tr(
                "Frag die KI nach typischen Berichtslinien und Teamgrößen für diese Rolle.",
                "Ask the AI for typical reporting lines and team sizes for this role.",
                lang=lang,
            )
        )

        if not state.get("started"):
            if st.button(
                tr("Assistent starten", "Launch assistant", lang=lang),
                type="secondary",
                key="team_advisor.start",
            ):
                state["started"] = True
                advice = advise_team_structure(state.get("messages"), profile, lang=lang)
                _record_advice(
                    advice,
                    state,
                    position=position,
                    update_profile=update_profile,
                    lang=lang,
                )
            return

        _render_chat_messages(state)
        _render_pending_actions(state, position, update_profile, lang)
        prompt = st.chat_input(
            tr("Frage stellen oder bestätigen …", "Ask or confirm …", lang=lang),
            key="team_advisor.input",
        )

        if prompt:
            _append_message(state, "user", prompt.strip())
            advice = advise_team_structure(state.get("messages"), profile, lang=lang, user_input=prompt)
            _record_advice(
                advice,
                state,
                position=position,
                update_profile=update_profile,
                lang=lang,
            )


__all__ = ["render_team_advisor"]
