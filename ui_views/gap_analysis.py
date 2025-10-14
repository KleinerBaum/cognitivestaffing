"""Gap analysis view for quick vacancy health checks."""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

import streamlit as st

from constants.keys import StateKeys
from question_logic import ask_followups, CRITICAL_FIELDS
from llm.client import extract_json
from llm.gap_analysis import analyze_vacancy
from state import ensure_state
from utils.i18n import tr

_RESULT_STATE_KEY = "gap_analysis.result"
_PROFILE_STATE_KEY = "gap_analysis.profile"
_FOLLOWUPS_STATE_KEY = "gap_analysis.followups"
_REPORT_STATE_KEY = "gap_analysis.assistant_report"
_TEXT_STATE_KEY = StateKeys.GAP_ANALYSIS_TEXT
_TITLE_STATE_KEY = StateKeys.GAP_ANALYSIS_TITLE


def _resolve_secret(name: str) -> str:
    """Return ``name`` from env or Streamlit secrets without raising errors."""

    env_value = os.getenv(name, "")
    resolved = env_value
    try:
        secrets_section = st.secrets.get("openai", {})  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - Streamlit secrets unavailable
        secrets_section = {}
    if isinstance(secrets_section, Mapping):
        resolved = str(secrets_section.get(name, resolved) or "")
    try:
        resolved = str(st.secrets.get(name, resolved))
    except Exception:  # pragma: no cover - Streamlit secrets unavailable
        resolved = resolved or ""
    return resolved.strip()


def _get_nested_value(payload: Mapping[str, Any], path: str) -> Any:
    """Return the value at ``path`` (dot-notation) from ``payload``."""

    current: Any = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _has_value(value: Any) -> bool:
    """Return ``True`` if ``value`` should be considered filled."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_value(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_value(item) for item in value)
    return True


def _compute_missing_fields(payload: Mapping[str, Any]) -> list[str]:
    """Return sorted list of critical fields missing from ``payload``."""

    missing: list[str] = []
    for field in sorted(CRITICAL_FIELDS):
        value = _get_nested_value(payload, field)
        if not _has_value(value):
            missing.append(field)
    return missing


def _format_field(field: str, *, lang: str) -> str:
    """Return a human-readable representation for ``field``."""

    arrow = " → " if lang == "de" else " → "
    return field.replace(".", arrow)


def _render_gap_report(lang: str) -> None:
    """Render the analysis result if present in session state."""

    result: Mapping[str, Any] | None = st.session_state.get(_RESULT_STATE_KEY)
    profile: Mapping[str, Any] | None = st.session_state.get(_PROFILE_STATE_KEY)
    followups: list[Mapping[str, Any]] = st.session_state.get(_FOLLOWUPS_STATE_KEY, [])
    report_text: str | None = st.session_state.get(_REPORT_STATE_KEY)

    if not result and not profile and not followups and not report_text:
        return

    st.divider()
    st.subheader(tr("Gap-Report", "Gap report", lang=lang))

    missing_fields: list[str] = list(result.get("missing_critical", [])) if result else []
    if missing_fields:
        st.markdown(tr("**Kritische Felder ohne Inhalte:**", "**Critical fields without data:**", lang=lang))
        for field in missing_fields:
            st.markdown(f"- `{_format_field(field, lang=lang)}`")
    else:
        st.success(
            tr(
                "Alle kritischen Felder sind aktuell befüllt.",
                "All critical fields are currently populated.",
                lang=lang,
            )
        )

    if report_text:
        st.markdown(tr("**Assistenten-Report**", "**Assistant report**", lang=lang))
        st.markdown(report_text)

    if followups:
        priority_order = {"critical": 0, "normal": 1, "optional": 2}
        sorted_followups = sorted(
            followups,
            key=lambda item: priority_order.get(str(item.get("priority", "")).lower(), 1),
        )
        st.markdown(tr("**Empfohlene Anschlussfragen:**", "**Recommended follow-up questions:**", lang=lang))
        for question in sorted_followups:
            text = str(question.get("question", "")).strip()
            priority = str(question.get("priority", "")).strip().lower()
            suggestions = [str(s).strip() for s in question.get("suggestions", []) if str(s).strip()]
            badge = {
                "critical": "🟥",
                "normal": "🟧",
                "optional": "🟩",
            }.get(priority, "🟦")
            field_label = str(question.get("field", "")).strip()
            if text:
                st.markdown(f"{badge} **{text}**")
            if field_label:
                st.caption(tr("Feld", "Field", lang=lang) + f": `{field_label}`")
            if suggestions:
                st.caption(tr("Vorschläge", "Suggestions", lang=lang) + ": " + ", ".join(suggestions))
    else:
        st.info(tr("Keine Anschlussfragen erforderlich.", "No follow-up questions required.", lang=lang))

    if profile:
        with st.expander(tr("JSON-Ergebnis anzeigen", "Show JSON output", lang=lang)):
            st.json(profile, expanded=False)


def run() -> None:
    """Render the gap analysis page."""

    ensure_state()
    lang = st.session_state.get("lang", "de")

    st.title(tr("Gap-Analyse", "Gap analysis", lang=lang))
    st.write(
        tr(
            "Analysiere einen Stellentext und identifiziere fehlende Pflichtfelder sowie Anschlussfragen.",
            "Analyse a vacancy text to identify missing critical fields and follow-up questions.",
            lang=lang,
        )
    )

    openai_key = _resolve_secret("OPENAI_API_KEY")
    vector_store_id = _resolve_secret("VECTOR_STORE_ID")
    if openai_key:
        st.session_state["openai_api_key_missing"] = False
    if vector_store_id:
        st.session_state.setdefault("vector_store_id", vector_store_id)

    with st.form("gap_analysis_form"):
        vacancy_text = st.text_area(
            tr("Stellentext", "Vacancy text", lang=lang),
            key=_TEXT_STATE_KEY,
            height=280,
            placeholder=tr(
                "Füge hier den vollständigen Ausschreibungstext ein…",
                "Paste the full job posting here…",
                lang=lang,
            ),
        )
        job_title = st.text_input(
            tr("Jobtitel (optional)", "Job title (optional)", lang=lang),
            key=_TITLE_STATE_KEY,
        )
        button_label = tr("Analysieren", "Analyze", lang=lang)
        submitted = st.form_submit_button(f"🚀 {button_label}", type="primary")

    if submitted:
        if not openai_key:
            st.error(
                tr(
                    "Kein OpenAI API-Schlüssel verfügbar. Bitte hinterlege ihn in den Streamlit Secrets oder der Umgebung.",
                    "No OpenAI API key available. Please configure it via Streamlit secrets or environment variables.",
                    lang=lang,
                )
            )
            return
        if not vacancy_text or not vacancy_text.strip():
            st.warning(
                tr(
                    "Bitte gib einen Stellentext ein, bevor du die Analyse startest.",
                    "Please provide a vacancy text before running the analysis.",
                    lang=lang,
                )
            )
            return

        st.session_state.pop(_RESULT_STATE_KEY, None)
        st.session_state.pop(_PROFILE_STATE_KEY, None)
        st.session_state.pop(_FOLLOWUPS_STATE_KEY, None)
        st.session_state.pop(_REPORT_STATE_KEY, None)

        analysis_caption = tr("Analysiere Stellenprofil…", "Analysing vacancy profile…", lang=lang)
        with st.spinner(analysis_caption):
            report_text = ""
            try:
                raw_json = extract_json(vacancy_text.strip(), title=job_title or None)
                profile_data = json.loads(raw_json)
                missing = _compute_missing_fields(profile_data)
                followup_payload = {
                    "data": profile_data,
                    "lang": lang,
                }
                followup_result = ask_followups(
                    followup_payload,
                    model=st.session_state.get("model"),
                    vector_store_id=(vector_store_id or None) or st.session_state.get("vector_store_id") or None,
                )
                questions = followup_result.get("questions", []) if isinstance(followup_result, Mapping) else []

                try:
                    assistant_result = analyze_vacancy(
                        vacancy_text.strip(),
                        job_title=job_title or None,
                        lang=lang,
                        vector_store_id=(vector_store_id or None) or st.session_state.get("vector_store_id") or None,
                    )
                    report_text = assistant_result.content
                except Exception as exc:  # pragma: no cover - network/SDK issues
                    report_text = ""
                    st.warning(
                        tr(
                            "LLM-Report nicht verfügbar: {error}",
                            "LLM report unavailable: {error}",
                            lang=lang,
                        ).format(error=str(exc))
                    )
            except Exception as exc:  # pragma: no cover - network/SDK issues
                st.error(
                    tr("Analyse fehlgeschlagen: {error}", "Analysis failed: {error}", lang=lang).format(error=str(exc))
                )
                return

        st.session_state[_PROFILE_STATE_KEY] = profile_data
        st.session_state[_RESULT_STATE_KEY] = {"missing_critical": missing}
        st.session_state[_FOLLOWUPS_STATE_KEY] = questions
        if report_text:
            st.session_state[_REPORT_STATE_KEY] = report_text
        st.success(tr("Analyse abgeschlossen.", "Analysis completed.", lang=lang))

    _render_gap_report(lang)
