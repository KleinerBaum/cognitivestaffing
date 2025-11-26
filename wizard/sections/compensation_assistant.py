"""Chat-style helper for proposing salary ranges on the compensation step."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, MutableMapping

import streamlit as st

from constants.keys import ProfilePaths, StateKeys, UIKeys
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from utils.i18n import tr
from utils.normalization import country_to_iso2
from wizard._logic import (
    _autofill_was_rejected,
    _clamp_salary_value,
    _infer_currency_from_range,
    _parse_salary_range_text,
    _record_autofill_rejection,
    _update_profile,
)


@dataclass(slots=True)
class SalarySuggestion:
    """Structured salary range suggestion."""

    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    source: str = "assistant"
    note: str | None = None
    raw_range: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)


def _format_currency(value: int, lang: str) -> str:
    formatted = f"{value:,.0f}"
    if lang == "de":
        formatted = formatted.replace(",", ".")
    return formatted


def _format_range_message(suggestion: SalarySuggestion, lang: str, *, job_title: str, country: str) -> str:
    salary_min = suggestion.salary_min or suggestion.salary_max
    salary_max = suggestion.salary_max or suggestion.salary_min
    currency = suggestion.currency or "EUR"
    if salary_min is None and salary_max is None:
        return tr(
            "Ich konnte keine verlässliche Gehaltsspanne finden. Bitte gib einen Budgetrahmen an, dann rechne ich ihn um.",
            "I could not find a reliable salary range. Please share your budget and I’ll convert it.",
            lang=lang,
        )
    formatted_min = _format_currency(salary_min or 0, lang)
    formatted_max = _format_currency(salary_max or salary_min or 0, lang)
    range_text = tr(
        "Vorschlag: {currency} {min}–{max} brutto/Jahr.",
        "Suggested: {currency} {min}–{max} gross/year.",
        lang=lang,
    ).format(currency=currency, min=formatted_min, max=formatted_max)
    context = []
    if job_title:
        context.append(job_title)
    if country:
        context.append(country)
    context_text = " · ".join(context)
    disclaimer = tr(
        "Band basierend auf Marktmedianen; bitte als Richtwert verstehen.",
        "Range reflects market medians; treat as a guide, not a guarantee.",
        lang=lang,
    )
    if suggestion.note:
        disclaimer = f"{disclaimer}\n\n{suggestion.note}"
    if context_text:
        return f"**{context_text}**\n{range_text}\n\n{disclaimer}"
    return f"{range_text}\n\n{disclaimer}"


def _collect_profile_context(profile: Mapping[str, Any]) -> tuple[str, str, str]:
    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    job_title = str(position.get("job_title") or "").strip()
    experience = str(position.get("seniority_level") or "").strip()
    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    country_raw = str(location.get("country") or "").strip()
    iso_country = country_to_iso2(country_raw) if country_raw else ""
    return job_title, iso_country or country_raw, experience


def _suggest_from_benchmark(job_title: str, country: str) -> SalarySuggestion:
    benchmark_role = resolve_salary_role(job_title) or job_title
    bench_country = country.upper().strip() if country else "US"
    benchmark = get_salary_benchmark(benchmark_role, bench_country)
    raw_range = str((benchmark or {}).get("salary_range") or "")
    salary_min, salary_max = _parse_salary_range_text(raw_range)
    currency = _infer_currency_from_range(raw_range)
    return SalarySuggestion(
        salary_min=salary_min,
        salary_max=salary_max,
        currency=currency,
        source="benchmark",
        note=None,
        raw_range=raw_range or None,
        debug={"role": benchmark_role, "country": bench_country},
    )


def _suggest_from_user_budget(message: str, currency_hint: str | None) -> SalarySuggestion | None:
    if not message:
        return None
    tokens = message.lower()
    monthly = any(keyword in tokens for keyword in ("month", "monat", "/mo"))
    matches = re.findall(r"\d+[\d,\.]*", message)
    if not matches:
        return None
    numbers: list[float] = []
    for raw in matches[:2]:
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            numbers.append(float(normalized))
        except ValueError:
            continue
    if not numbers:
        return None
    multiplier = 1_000 if "k" in tokens else 1
    values = [int(round(number * multiplier)) for number in numbers]
    if monthly:
        values = [value * 12 for value in values]
    if len(values) == 1:
        value = values[0]
        salary_min = int(round(value * 0.9))
        salary_max = int(round(value * 1.1))
    else:
        salary_min, salary_max = values[0], values[1]
        if salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min
    return SalarySuggestion(
        salary_min=salary_min,
        salary_max=salary_max,
        currency=currency_hint,
        source="user_budget",
        note=tr(
            "Spanne aus deiner Angabe abgeleitet (inkl. 10 % Puffer).",
            "Derived from your input with a 10% buffer.",
            lang=st.session_state.get("lang", "de"),
        ),
    )


def _normalize_conflict_value(value: Any) -> str:
    """Return a trimmed representation for conflict comparison."""

    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value))
    return " ".join(str(value).strip().split())


def _sync_salary_state(compensation: Mapping[str, Any], source: str) -> None:
    """Persist the applied salary values into session state."""

    salary_min = _clamp_salary_value(compensation.get("salary_min"))
    salary_max = _clamp_salary_value(compensation.get("salary_max"))
    currency = str(compensation.get("currency") or "").strip()
    st.session_state[UIKeys.SALARY_ESTIMATE] = {
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "source": source,
    }
    st.session_state[UIKeys.SALARY_REFRESH] = datetime.utcnow().isoformat()
    st.session_state["ui.compensation.salary_range"] = (salary_min, salary_max)


def _apply_salary_provided(compensation: MutableMapping[str, Any]) -> bool:
    """Update and return the provided flag for compensation data."""

    provided = bool(compensation.get("salary_min") or compensation.get("salary_max"))
    compensation["salary_provided"] = provided
    _update_profile(ProfilePaths.COMPENSATION_SALARY_PROVIDED, provided, mark_ai=True)
    return provided


def _queue_salary_conflicts(
    *,
    profile: MutableMapping[str, Any],
    suggestion: SalarySuggestion,
    state: MutableMapping[str, Any],
) -> None:
    """Store conflicts for manual confirmation before applying."""

    compensation = profile.setdefault("compensation", {})
    conflict_entries: list[dict[str, Any]] = []
    applied_any = False

    field_meta = (
        (
            ProfilePaths.COMPENSATION_SALARY_MIN,
            "salary_min",
            tr("Aktuelles Minimum", "Current minimum"),
            compensation.get("salary_min"),
            suggestion.salary_min,
        ),
        (
            ProfilePaths.COMPENSATION_SALARY_MAX,
            "salary_max",
            tr("Aktuelles Maximum", "Current maximum"),
            compensation.get("salary_max"),
            suggestion.salary_max,
        ),
        (
            ProfilePaths.COMPENSATION_CURRENCY,
            "currency",
            tr("Aktuelle Währung", "Current currency"),
            compensation.get("currency"),
            suggestion.currency or "EUR",
        ),
    )

    for path, comp_key, label, current, proposed in field_meta:
        normalized_current = _normalize_conflict_value(current)
        normalized_proposed = _normalize_conflict_value(proposed)
        if not normalized_proposed:
            continue
        if not normalized_current:
            _update_profile(path, proposed, mark_ai=True)
            compensation[comp_key] = proposed
            applied_any = True
            continue
        if _autofill_was_rejected(path, str(proposed or "")):
            continue
        if normalized_current != normalized_proposed:
            conflict_entries.append(
                {
                    "path": path,
                    "comp_key": comp_key,
                    "label": label,
                    "current": str(current or ""),
                    "proposed": str(proposed or ""),
                }
            )

    if conflict_entries:
        suggestion_token = f"{suggestion.salary_min}:{suggestion.salary_max}:{suggestion.currency}"
        state["pending_conflicts"] = {
            "fields": conflict_entries,
            "suggestion_token": suggestion_token,
            "source": suggestion.source,
        }
        st.session_state[StateKeys.COMPENSATION_ASSISTANT] = state
        if applied_any:
            _apply_salary_provided(compensation)
            _sync_salary_state(compensation, suggestion.source)
    else:
        if applied_any:
            _apply_salary_provided(compensation)
            _sync_salary_state(compensation, suggestion.source)
        st.toast(
            tr("Spanne übernommen.", "Salary range applied.", lang=st.session_state.get("lang", "de")),
            icon="✅",
        )


def _render_conflict_confirmation(profile: MutableMapping[str, Any], state: MutableMapping[str, Any]) -> None:
    """Display a confirmation UI for conflicting salary suggestions."""

    pending = state.get("pending_conflicts")
    if not pending:
        return

    conflicts: list[Mapping[str, Any]] = pending.get("fields", [])
    if not conflicts:
        state.pop("pending_conflicts", None)
        st.session_state[StateKeys.COMPENSATION_ASSISTANT] = state
        return

    lang = st.session_state.get("lang", "de")
    suggestion_token = str(pending.get("suggestion_token") or "")
    selection_key = f"salary_conflict_selection.{suggestion_token}"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = {entry["path"]: True for entry in conflicts}

    st.markdown("### 🤖➜✍️ " + tr("Vorschlag bestätigen", "Confirm AI proposal", lang=lang))
    st.caption(
        tr(
            "KI möchte bestehende Werte überschreiben. Prüfe Unterschiede und entscheide pro Feld oder für alle.",
            "The assistant wants to overwrite existing values. Review the differences and decide per field or in bulk.",
            lang=lang,
        )
    )

    for entry in conflicts:
        path = str(entry.get("path"))
        label = str(entry.get("label") or path)
        current_value = str(entry.get("current") or "")
        proposed_value = str(entry.get("proposed") or "")
        with st.container(border=True):
            cols = st.columns([0.1, 0.45, 0.45])
            is_selected = cols[0].checkbox(
                "",
                key=f"{selection_key}.{path}",
                value=st.session_state[selection_key].get(path, True),
            )
            st.session_state[selection_key][path] = is_selected
            cols[1].markdown(f"**{tr('Meine Angabe', 'My input', lang=lang)} – {label}**")
            cols[1].code(current_value or tr("(leer)", "(empty)", lang=lang))
            cols[2].markdown(f"**{tr('KI-Vorschlag', 'AI suggestion', lang=lang)} – {label}**")
            cols[2].code(proposed_value)

    apply_selected = st.button(
        tr("AI-Wert übernehmen", "Accept AI suggestion", lang=lang),
        type="primary",
        key=f"apply_selected.{suggestion_token}",
    )
    apply_all = st.button(
        tr("Alle Felder übernehmen", "Accept for all fields", lang=lang),
        key=f"apply_all.{suggestion_token}",
    )
    keep_manual = st.button(
        tr("Meine Werte behalten", "Keep my version", lang=lang),
        key=f"keep_manual.{suggestion_token}",
    )

    def _apply_conflicts(selected_paths: set[str]) -> None:
        compensation = profile.setdefault("compensation", {})
        for entry in conflicts:
            path = str(entry.get("path"))
            proposed_value = entry.get("proposed")
            comp_key = str(entry.get("comp_key"))
            if path in selected_paths:
                _update_profile(path, proposed_value, mark_ai=True)
                compensation[comp_key] = proposed_value
            else:
                _record_autofill_rejection(path, str(proposed_value or ""))
        _apply_salary_provided(compensation)
        _sync_salary_state(compensation, str(pending.get("source") or "assistant"))
        state.pop("pending_conflicts", None)
        st.session_state[StateKeys.COMPENSATION_ASSISTANT] = state
        st.toast(
            tr("Entscheidung gespeichert.", "Choice saved.", lang=lang),
            icon="✅",
        )
        st.rerun()

    if apply_all:
        _apply_conflicts({str(entry.get("path")) for entry in conflicts})
    elif apply_selected:
        selected = {
            path
            for path in st.session_state.get(selection_key, {})
            if st.session_state[selection_key].get(path)
        }
        _apply_conflicts(selected)
    elif keep_manual:
        _apply_conflicts(set())


def render_compensation_assistant(profile: MutableMapping[str, Any]) -> None:
    """Render the AI compensation assistant inside an expander."""

    lang = st.session_state.get("lang", "de")
    job_title, country, experience = _collect_profile_context(profile)
    state = st.session_state.setdefault(
        StateKeys.COMPENSATION_ASSISTANT,
        {"messages": [], "last_suggestion": None, "counter": 0},
    )

    with st.expander(tr("💬 Gehaltsassistent", "💬 Salary assistant", lang=lang), expanded=False):
        if not state["messages"]:
            intro = tr(
                "Ich helfe dir, eine realistische Gehaltsspanne zu setzen – mit Marktbezug oder basierend auf deinem Budget.",
                "I can propose a realistic salary range with market context or convert your stated budget.",
                lang=lang,
            )
            hints = []
            if job_title:
                hints.append(tr("Rolle: {job}", "Role: {job}", lang=lang).format(job=job_title))
            if country:
                hints.append(tr("Land: {country}", "Country: {country}", lang=lang).format(country=country))
            if experience:
                hints.append(tr("Erfahrung: {level}", "Seniority: {level}", lang=lang).format(level=experience))
            if hints:
                intro = f"{intro}\n\n" + " · ".join(hints)
            state["messages"].append({"role": "assistant", "content": intro})

        for message in state.get("messages", []):
            content = str(message.get("content") or "").strip()
            role = str(message.get("role") or "assistant")
            if content:
                st.chat_message(role).markdown(content)

        col1, col2 = st.columns(2)
        if col1.button(
            tr("Marktspanne abrufen", "Fetch market range", lang=lang),
            disabled=not job_title,
            help=tr(
                "Nutze Benchmark-Daten für die Rolle und das Land.",
                "Use benchmark data for the role and country.",
                lang=lang,
            ),
        ):
            suggestion = _suggest_from_benchmark(job_title, country)
            message = _format_range_message(suggestion, lang, job_title=job_title, country=country)
            state.setdefault("messages", []).append({"role": "assistant", "content": message})
            state["last_suggestion"] = suggestion
            state["counter"] = state.get("counter", 0) + 1

        prompt = col2.chat_input(
            tr("Budget oder Frage eingeben…", "Share your budget or ask a question…", lang=lang),
            disabled=False,
        )

        _render_conflict_confirmation(profile, state)

        if prompt:
            normalized = prompt.strip()
            if normalized:
                state.setdefault("messages", []).append({"role": "user", "content": normalized})
                suggestion = _suggest_from_user_budget(normalized, profile.get("compensation", {}).get("currency"))
                if suggestion:
                    message = _format_range_message(suggestion, lang, job_title=job_title, country=country)
                    state.setdefault("messages", []).append({"role": "assistant", "content": message})
                    state["last_suggestion"] = suggestion
                else:
                    fallback = tr(
                        'Ich kann deinen Hinweis nicht als Zahl lesen. Klicke auf "Marktspanne abrufen" oder nenne einen Betrag (z. B. 5500 €/Monat).',
                        'I couldn’t read a number. Use "Fetch market range" or share an amount (e.g. 5500 €/month).',
                        lang=lang,
                    )
                    state.setdefault("messages", []).append({"role": "assistant", "content": fallback})

        suggestion = state.get("last_suggestion")
        if (
            isinstance(suggestion, SalarySuggestion)
            and suggestion.salary_min is not None
            and suggestion.salary_max is not None
        ):
            apply_label = tr("Spanne übernehmen", "Apply suggested range", lang=lang)
            tooltip = tr(
                "Setzt Minimum, Maximum und Währung im Formular.",
                "Writes min, max, and currency into the form.",
                lang=lang,
            )
            if st.button(apply_label, key=f"apply_salary_{state.get('counter', 0)}", help=tooltip):
                _queue_salary_conflicts(profile=profile, suggestion=suggestion, state=state)
                if not state.get("pending_conflicts"):
                    confirmation = tr(
                        "Erledigt – Spanne und Währung wurden eingetragen.",
                        "Done — range and currency have been set.",
                        lang=lang,
                    )
                    state.setdefault("messages", []).append({"role": "assistant", "content": confirmation})

        st.session_state[StateKeys.COMPENSATION_ASSISTANT] = state
