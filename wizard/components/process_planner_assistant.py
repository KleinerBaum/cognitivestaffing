"""Interactive assistant for planning the hiring process."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

import streamlit as st

import config as app_config
from config import ModelTask, get_model_for
from openai_utils.api import call_chat_api
from openai_utils.tools import build_function_tools
from state.ai_failures import (
    increment_step_failure,
    is_step_ai_skipped,
    reset_step_failures,
)
from utils.i18n import tr
from utils.llm_state import is_llm_available, llm_disabled_message
from constants.keys import StateKeys
from wizard._logic import _update_profile
from wizard.ai_skip import render_skip_cta, render_skipped_banner

PLANNER_STATE_KEY: Final[str] = "wizard.process_planner.state"
PLANNER_UI_KEY: Final[str] = "ui.process.hiring_process"


def normalize_hiring_process_steps(value: object) -> list[str]:
    """Return a cleaned list of hiring process steps from ``value``."""

    if value is None:
        return []

    def _clean_pool(pool: Sequence[str]) -> list[str]:
        cleaned: list[str] = []
        for entry in pool:
            if not isinstance(entry, str):
                continue
            stripped = entry.strip()
            stripped = stripped.lstrip("-•").strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned

    if isinstance(value, str):
        parts = re.split(r"[\n|]+", value)
        return _clean_pool(parts)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _clean_pool(list(value))

    return []


def format_hiring_process_text(steps: Sequence[str]) -> str:
    """Join ``steps`` into a textarea-friendly format."""

    return "\n".join(step for step in steps if isinstance(step, str) and step.strip())


def _context_token(lang: str, job_title: str, seniority: str | None) -> str:
    """Return a token representing the current conversation context."""

    return "|".join([lang or "", job_title or "", seniority or ""])


def _resolve_role_context(profile: Mapping[str, Any]) -> tuple[str, str | None]:
    """Return the role title and seniority level from ``profile``."""

    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    job_title = str(position.get("job_title") or "").strip()
    seniority_raw = position.get("seniority_level")
    seniority_str = str(seniority_raw).strip() if seniority_raw is not None else ""
    return job_title, (seniority_str or None)


def _build_system_prompt(
    *,
    lang: str,
    job_title: str,
    seniority: str | None,
    existing_steps: Sequence[str],
) -> str:
    """Return a localized system prompt for the planner agent."""

    seniority_fragment = f" (Level: {seniority})" if seniority else ""
    existing_plan = format_hiring_process_text(existing_steps)
    base_prompt_en = (
        "You are an HR specialist helping to design a hiring process. "
        "Suggest a concise, ordered list of interview stages tailored to the role "
        f"{job_title or 'the role'}{seniority_fragment}. "
        "Recommend 3–6 stages such as screening calls, technical interviews, presentations, or executive rounds, "
        "adjusting complexity to the seniority level. Present the stages as a numbered list, then ask whether to add, "
        "remove, or reorder anything. Once the user approves the final order, call set_hiring_process with all steps "
        "joined by ' | ' in the confirmed sequence."
    )
    base_prompt_de = (
        "Du bist HR-Spezialist:in und hilfst dabei, einen Bewerbungsprozess zu gestalten. "
        "Schlage eine geordnete Liste von Interview-Phasen vor, zugeschnitten auf die Rolle "
        f"{job_title or 'die Rolle'}{seniority_fragment}. "
        "Empfiehl 3–6 Schritte wie Screening-Call, fachliches Interview, Case/Präsentation oder Executive-Runde und "
        "passe die Komplexität an die Seniorität an. Präsentiere die Schritte nummeriert und frage nach Ergänzungen, "
        "Entfernungen oder einer anderen Reihenfolge. Sobald der finale Ablauf bestätigt ist, rufe set_hiring_process "
        "mit allen Schritten auf, verbunden durch ' | ' in der bestätigten Reihenfolge."
    )
    prompt = base_prompt_de if lang.startswith("de") else base_prompt_en
    if existing_plan:
        plan_intro = tr(
            "Vorhandener Plan:\n{plan}",
            "Existing plan:\n{plan}",
            lang=lang,
        ).format(plan=existing_plan)
        prompt = f"{prompt}\n\n{plan_intro}"
    return prompt


def _get_state() -> dict[str, Any]:
    """Return the persisted planner state."""

    state = st.session_state.get(PLANNER_STATE_KEY)
    if not isinstance(state, dict):
        state = {"messages": [], "last_plan": [], "context_token": ""}
    state.setdefault("messages", [])
    state.setdefault("last_plan", [])
    state.setdefault("context_token", "")
    st.session_state[PLANNER_STATE_KEY] = state
    return state


def _set_hiring_process_tool(steps: str) -> dict[str, Any]:
    """Persist the confirmed hiring process steps in the profile."""

    plan = normalize_hiring_process_steps(steps)
    state = _get_state()
    state["last_plan"] = plan
    st.session_state[PLANNER_STATE_KEY] = state

    _update_profile("process.hiring_process", plan, session_value=plan)
    st.session_state[PLANNER_UI_KEY] = format_hiring_process_text(plan)
    st.toast(
        tr(
            "Prozessplan übernommen – die Schritte wurden gespeichert.",
            "Plan applied – the steps have been saved.",
            lang=st.session_state.get("lang", "de"),
        )
    )
    return {"saved_steps": plan}


def _run_planner_turn(
    *,
    state: dict[str, Any],
    user_message: str | None,
    lang: str,
    job_title: str,
    seniority: str | None,
    existing_steps: Sequence[str],
) -> bool:
    """Execute a single planner turn and append the assistant reply."""

    system_prompt = _build_system_prompt(
        lang=lang,
        job_title=job_title,
        seniority=seniority,
        existing_steps=existing_steps,
    )
    if user_message:
        state.setdefault("messages", []).append({"role": "user", "content": user_message})

    tools, tool_functions = build_function_tools(
        {
            "set_hiring_process": {
                "description": (
                    "Store the confirmed hiring process steps. Provide all steps as a single string separated by ' | '."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "string",
                            "description": "All hiring process steps separated by ' | '.",
                        }
                    },
                    "required": ["steps"],
                },
            }
        },
        callables={"set_hiring_process": _set_hiring_process_tool},
    )

    with st.spinner(tr("Prozess wird geplant…", "Planning the process…", lang=lang)):
        try:
            result = call_chat_api(
                messages=[{"role": "system", "content": system_prompt}, *state.get("messages", [])],
                model=get_model_for(ModelTask.TASK_SUGGESTION),
                temperature=0.2,
                reasoning_effort=st.session_state.get(StateKeys.REASONING_EFFORT, app_config.REASONING_EFFORT),
                tools=tools,
                tool_choice="auto",
                tool_functions=tool_functions,
                include_analysis_tools=False,
                task=ModelTask.TASK_SUGGESTION,
            )
        except Exception as exc:  # pragma: no cover - network/runtime guard
            st.error(
                tr(
                    "Assistent konnte nicht antworten: {error}",
                    "Assistant could not respond: {error}",
                    lang=lang,
                    ).format(error=exc)
            )
            increment_step_failure("process")
            render_skip_cta(
                "process",
                lang=lang,
                warning_text=(
                    "KI-Antworten sind mehrfach fehlgeschlagen. Du kannst die Planung überspringen und Schritte manuell erfassen.",
                    "AI replies failed repeatedly. Skip the planner and capture the steps manually instead.",
                ),
                button_key="process_planner.skip.error",
            )
            return False

    reset_step_failures("process")

    assistant_reply = (result.content or "").strip()
    if assistant_reply:
        state.setdefault("messages", []).append({"role": "assistant", "content": assistant_reply})
    st.session_state[PLANNER_STATE_KEY] = state
    return True


def render_process_planner_assistant(profile: Mapping[str, Any], *, lang: str) -> None:
    """Render the hiring process planner assistant."""

    job_title, seniority = _resolve_role_context(profile)
    process_data = profile.get("process", {}) if isinstance(profile, Mapping) else {}
    existing_steps = normalize_hiring_process_steps(process_data.get("hiring_process"))

    state = _get_state()
    token = _context_token(lang, job_title, seniority)
    if state.get("context_token") != token:
        state = {"messages": [], "last_plan": normalize_hiring_process_steps(existing_steps), "context_token": token}
        st.session_state[PLANNER_STATE_KEY] = state

    if existing_steps and not state.get("last_plan"):
        state["last_plan"] = existing_steps
        st.session_state[PLANNER_STATE_KEY] = state

    with st.expander(tr("💡 KI-Prozessplaner", "💡 AI process planner"), expanded=False):
        st.caption(
            tr(
                "Lass dir einen passenden Interview-Ablauf vorschlagen und passe die Reihenfolge an, bevor er gespeichert wird.",
                "Get a suggested interview flow and adjust the order before saving it to the profile.",
                lang=lang,
            )
        )

        if is_step_ai_skipped("process"):
            render_skipped_banner(
                "process",
                lang=lang,
                message=(
                    "KI-Vorschläge für den Prozess wurden übersprungen. Du kannst die Schritte unten manuell pflegen.",
                    "AI suggestions for the process were skipped. Continue managing the steps manually below.",
                ),
            )
            return

        render_skip_cta(
            "process",
            lang=lang,
            warning_text=(
                "Mehrere Fehlversuche erkannt – überspringe den KI-Planer, wenn du die Schritte manuell eingeben möchtest.",
                "Multiple failed attempts detected – skip the AI planner if you prefer to enter steps manually.",
            ),
            button_key="process_planner.skip.cta",
        )

        if not is_llm_available():
            st.info(llm_disabled_message())
            return

        if state.get("last_plan"):
            st.markdown(tr("Aktueller Plan", "Current plan", lang=lang))
            st.markdown("\n".join(f"- {step}" for step in state.get("last_plan", [])))

        if not state.get("messages"):
            if st.button(
                tr("Prozessvorschlag anfordern", "Request process proposal", lang=lang),
                use_container_width=True,
            ):
                _run_planner_turn(
                    state=state,
                    user_message=tr(
                        "Bitte schlage einen strukturierten Bewerbungsprozess vor.",
                        "Please suggest a structured hiring process.",
                        lang=lang,
                    ),
                    lang=lang,
                    job_title=job_title,
                    seniority=seniority,
                    existing_steps=existing_steps,
                )
        else:
            for message in state.get("messages", []):
                role = message.get("role") or "assistant"
                content = str(message.get("content") or "")
                if not content.strip():
                    continue
                st.chat_message(role).markdown(content)

        prompt = st.chat_input(tr("Anpassung eingeben…", "Share an adjustment…", lang=lang))
        if prompt is not None:
            normalized_prompt = prompt.strip()
            if normalized_prompt:
                _run_planner_turn(
                    state=state,
                    user_message=normalized_prompt,
                    lang=lang,
                    job_title=job_title,
                    seniority=seniority,
                    existing_steps=existing_steps,
                )
            else:
                st.toast(
                    tr(
                        "Bitte gib eine Änderung oder Bestätigung ein.",
                        "Please provide a change or confirmation.",
                        lang=lang,
                    )
                )
