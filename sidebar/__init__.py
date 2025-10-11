from __future__ import annotations

import html
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from core.preview import build_prefilled_sections, preview_value_to_text
from utils.i18n import tr
from utils.usage import build_usage_markdown, usage_totals

from wizard import FIELD_SECTION_MAP, get_missing_critical_fields

from .salary import estimate_salary_expectation


STEP_LABELS: list[tuple[str, str]] = [
    ("onboarding", tr("Onboarding", "Onboarding")),
    ("company", tr("Unternehmen", "Company")),
    ("basic", tr("Basisdaten", "Basic info")),
    ("requirements", tr("Anforderungen", "Requirements")),
    ("compensation", tr("Leistungen & Benefits", "Rewards & Benefits")),
    ("process", tr("Prozess", "Process")),
    ("summary", tr("Summary", "Summary")),
]

@dataclass(slots=True)
class SidebarContext:
    """Convenience bundle with precomputed sidebar data."""

    profile: Mapping[str, Any]
    extraction_summary: Mapping[str, Any]
    skill_buckets: Mapping[str, Iterable[str]]
    missing_fields: set[str]
    missing_by_section: dict[int, list[str]]
    prefilled_sections: list[tuple[str, list[tuple[str, Any]]]]


def render_sidebar() -> None:
    """Render the dynamic wizard sidebar with contextual content."""

    _ensure_ui_defaults()

    context = _build_context()

    with st.sidebar:
        _render_settings()
        _render_hero(context)
        st.divider()
        _render_step_context(context)
        st.divider()
        _render_salary_expectation(context.profile)


def _ensure_ui_defaults() -> None:
    """Initialise language and theme toggles in session state."""

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")
    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]
    if "ui.lang_toggle" not in st.session_state:
        st.session_state["ui.lang_toggle"] = (
            st.session_state[UIKeys.LANG_SELECT] == "en"
        )
    if "ui.dark_mode" not in st.session_state:
        st.session_state["ui.dark_mode"] = st.session_state.get("dark_mode", True)


def _build_context() -> SidebarContext:
    """Collect data used across sidebar sections."""

    profile: Mapping[str, Any] = st.session_state.get(StateKeys.PROFILE, {})
    summary: Mapping[str, Any] = st.session_state.get(StateKeys.EXTRACTION_SUMMARY, {})
    skill_buckets: Mapping[str, Iterable[str]] = st.session_state.get(
        StateKeys.SKILL_BUCKETS, {}
    )

    missing = set(get_missing_critical_fields())
    missing_by_section: dict[int, list[str]] = {}
    for field in missing:
        section = FIELD_SECTION_MAP.get(field)
        if section is None:
            continue
        missing_by_section.setdefault(section, []).append(field)

    prefilled_sections = build_prefilled_sections()

    return SidebarContext(
        profile=profile,
        extraction_summary=summary,
        skill_buckets=skill_buckets,
        missing_fields=missing,
        missing_by_section=missing_by_section,
        prefilled_sections=prefilled_sections,
    )


def _render_settings() -> None:
    """Show language and theme controls."""

    def _on_theme_toggle() -> None:
        st.session_state["dark_mode"] = st.session_state["ui.dark_mode"]

    def _on_lang_toggle() -> None:
        st.session_state[UIKeys.LANG_SELECT] = (
            "en" if st.session_state["ui.lang_toggle"] else "de"
        )
        st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    st.markdown(f"### ⚙️ {tr('Einstellungen', 'Settings')}")
    dark_col, lang_col = st.columns(2)
    with dark_col:
        st.toggle(
            tr("Dunkelmodus 🌙", "Dark mode 🌙"),
            key="ui.dark_mode",
            on_change=_on_theme_toggle,
        )
    with lang_col:
        st.toggle(
            tr("🇩🇪 Deutsch", "🇬🇧 English"),
            key="ui.lang_toggle",
            on_change=_on_lang_toggle,
        )


def _render_hero(context: SidebarContext) -> None:
    """Render extracted data grouped by wizard step."""

    st.markdown(f"### 🗂️ {tr('Schnellüberblick', 'Quick snapshot')}")

    step_order, step_entries = _build_initial_extraction_entries(context)
    if not any(step_entries.values()):
        st.caption(
            tr(
                "Sobald du Daten importierst, erscheinen hier die wichtigsten Ergebnisse.",
                "As soon as you import data the top findings will appear here.",
            )
        )
        return

    step_labels = {key: label for key, label in STEP_LABELS}
    for idx, step_key in enumerate(step_order):
        entries = step_entries.get(step_key, [])
        if not entries:
            continue
        label = step_labels.get(step_key, step_key.title())
        with st.expander(label, expanded=idx == 0):
            for field_label, value in entries:
                safe_label = html.escape(field_label)
                safe_value = html.escape(value)
                st.markdown(
                    f"- **{safe_label}**: {safe_value}",
                    unsafe_allow_html=True,
                )

def _render_step_context(context: SidebarContext) -> None:
    """Render contextual guidance for the active wizard step."""

    current = st.session_state.get(StateKeys.STEP, 0)

    renderers = {
        0: _render_onboarding_context,
        1: _render_company_context,
        2: _render_basic_context,
        3: _render_requirements_context,
        4: _render_compensation_context,
        5: _render_process_context,
        6: _render_summary_context,
    }
    renderer = renderers.get(current)
    if renderer is None:
        st.markdown(f"### 🧭 {tr('Kontext zum Schritt', 'Step context')}")
        st.caption(tr("Keine Kontextinformationen verfügbar.", "No context available."))
        return

    if current != 0:
        st.markdown(f"### 🧭 {tr('Kontext zum Schritt', 'Step context')}")

    renderer(context)


def _build_initial_extraction_entries(
    context: SidebarContext,
) -> tuple[list[str], dict[str, list[tuple[str, str]]]]:
    """Return ordered step keys with their extracted entries."""

    step_order = [key for key, _ in STEP_LABELS]
    if not step_order:
        return [], {}

    step_entries: dict[str, list[tuple[str, str]]] = {key: [] for key in step_order}

    summary = context.extraction_summary
    known_step_keys = set(step_order)
    if isinstance(summary, Mapping):
        is_step_grouped = (
            summary
            and all(
                isinstance(value, Mapping) and key in known_step_keys
                for key, value in summary.items()
            )
        )
        if is_step_grouped:
            for step_key, values in summary.items():
                entries = step_entries.setdefault(step_key, [])
                for label, value in values.items():
                    preview = preview_value_to_text(value)
                    if preview:
                        entries.append((str(label), preview))
        else:
            entries = step_entries.setdefault("onboarding", [])
            for label, value in summary.items():
                preview = preview_value_to_text(value)
                if preview:
                    entries.append((str(label), preview))

    section_map = _initial_extraction_section_map()
    for section_label, items in context.prefilled_sections:
        step_key = section_map.get(section_label)
        if not step_key:
            continue
        entries = step_entries.setdefault(step_key, [])
        for path, value in items:
            preview = preview_value_to_text(value)
            if not preview:
                continue
            entries.append((_format_field_name(path), preview))

    return step_order, step_entries


def _initial_extraction_section_map() -> dict[str, str]:
    """Return mapping of section labels to wizard step keys."""

    return {
        tr("Unternehmen", "Company"): "company",
        tr("Basisdaten", "Basic info"): "basic",
        tr("Beschäftigung", "Employment"): "basic",
        tr("Anforderungen", "Requirements"): "requirements",
        tr("Leistungen & Benefits", "Rewards & Benefits"): "compensation",
        tr("Prozess", "Process"): "process",
    }


def _render_onboarding_context(_: SidebarContext) -> None:
    missing = st.session_state.get(StateKeys.EXTRACTION_MISSING, [])
    if missing:
        st.warning(
            tr(
                "Folgende Pflichtfelder fehlen noch: ",
                "The following critical fields are still missing: ",
            )
            + ", ".join(_format_field_name(item) for item in missing[:6])
        )


def _render_company_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Unternehmensdaten', 'Company details')}")
    company = context.profile.get("company", {})
    if not company:
        st.caption(tr("Noch keine Firmendaten hinterlegt.", "No company details yet."))
        return
    for key in ("name", "industry", "hq_location", "size", "mission"):
        value = company.get(key)
        if value:
            st.markdown(f"- **{_format_field_name(f'company.{key}')}**: {value}")

    _render_missing_hint(context, section=1)


def _render_basic_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Rollenüberblick', 'Role snapshot')}")
    position = context.profile.get("position", {})
    location = context.profile.get("location", {})
    if not position and not location:
        st.caption(tr("Noch keine Basisdaten hinterlegt.", "No basic info yet."))
    else:
        for key in ("job_title", "seniority_level", "department"):
            value = position.get(key)
            if value:
                st.markdown(f"- **{_format_field_name(f'position.{key}')}**: {value}")
        city = location.get("primary_city")
        country = location.get("country")
        if city or country:
            st.markdown(
                f"- **{tr('Standort', 'Location')}:** {', '.join(part for part in [city, country] if part)}"
            )
    employment = context.profile.get("employment", {})
    if employment.get("work_policy"):
        policy = employment["work_policy"]
        st.caption(
            tr("Aktuelle Arbeitsform:", "Current work policy:") + f" {policy}"
        )
    _render_missing_hint(context, section=2)


def _render_requirements_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Skill-Portfolio', 'Skill portfolio')}")
    must = list(context.skill_buckets.get("must", []))
    nice = list(context.skill_buckets.get("nice", []))
    if not must and not nice:
        st.caption(
            tr(
                "Lege Must-have und Nice-to-have Skills fest, um das Profil zu schärfen.",
                "Add must-have and nice-to-have skills to sharpen the profile.",
            )
        )
    if must:
        st.markdown(f"**{tr('Must-haves', 'Must-haves')}**: {', '.join(must[:12])}")
    if nice:
        st.markdown(f"**{tr('Nice-to-haves', 'Nice-to-haves')}**: {', '.join(nice[:12])}")
    missing_esco = [
        str(skill).strip()
        for skill in st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
        if isinstance(skill, str) and str(skill).strip()
    ]
    if missing_esco:
        outstanding = ", ".join(dict.fromkeys(missing_esco))
        st.warning(
            tr(
                "ESCO meldet noch fehlende Essentials: {skills}",
                "ESCO still flags missing essentials: {skills}",
            ).format(skills=outstanding)
        )
    _render_missing_hint(context, section=3)


def _render_compensation_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Vergütung & Benefits', 'Compensation & benefits')}")
    compensation = context.profile.get("compensation", {})
    salary_min = compensation.get("salary_min")
    salary_max = compensation.get("salary_max")
    currency = compensation.get("currency") or ""
    if salary_min or salary_max:
        st.markdown(
            f"- **{tr('Aktuelle Spanne', 'Current range')}**: {_format_salary_range(salary_min, salary_max, currency)}"
        )
    if compensation.get("variable_pay"):
        st.markdown(f"- **{tr('Variable Vergütung', 'Variable pay')}**: ✅")
    benefits = compensation.get("benefits", [])
    if benefits:
        st.markdown(
            f"- **{tr('Benefits', 'Benefits')}**: {', '.join(benefits[:8])}"
        )
    if not (salary_min or salary_max or benefits):
        st.caption(
            tr(
                "Trage Gehaltsdaten und Benefits ein, um Erwartungen abgleichen zu können.",
                "Add salary details and benefits to compare expectations.",
            )
        )


def _render_process_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Hiring-Prozess', 'Hiring process')}")
    process = context.profile.get("process", {})
    stakeholders = process.get("stakeholders", [])
    phases = process.get("phases", [])
    if stakeholders:
        lead = next((s for s in stakeholders if s.get("primary")), None)
        if lead:
            st.markdown(
                f"- **{tr('Lead Recruiter', 'Lead recruiter')}**: {lead.get('name', '')}"
            )
        st.markdown(
            f"- **{tr('Stakeholder gesamt', 'Stakeholders total')}**: {len(stakeholders)}"
        )
    if phases:
        st.markdown(
            f"- **{tr('Prozessphasen', 'Process phases')}**: {len(phases)}"
        )
    if process.get("notes"):
        st.caption(f"{tr('Hinweis', 'Note')}: {process['notes']}")
    if not (stakeholders or phases or process.get("notes")):
        st.caption(
            tr(
                "Lege Verantwortliche und Phasen fest, um einen transparenten Ablauf zu sichern.",
                "Define stakeholders and phases to keep the process transparent.",
            )
        )


def _render_summary_context(context: SidebarContext) -> None:
    st.markdown(f"#### {tr('Bereit für den Export', 'Export readiness')}")
    downloads = [
        (UIKeys.JOB_AD_OUTPUT, tr("Job-Ad erstellt", "Job ad generated")),
        (UIKeys.INTERVIEW_OUTPUT, tr("Interview-Guide erstellt", "Interview guide generated")),
    ]
    for key, label in downloads:
        available = bool(st.session_state.get(key))
        icon = "✅" if available else "⏳"
        st.markdown(f"- {icon} {label}")

    usage = st.session_state.get(StateKeys.USAGE)
    if usage:
        in_tok, out_tok, total_tok = usage_totals(usage)
        summary = (
            tr("Tokenverbrauch", "Token usage")
            + f": {in_tok} + {out_tok} = {total_tok}"
        )
        table = build_usage_markdown(usage)
        if table:
            with st.expander(summary):
                st.markdown(table)
        else:
            st.caption(summary)


def _render_missing_hint(context: SidebarContext, *, section: int) -> None:
    missing = context.missing_by_section.get(section, [])
    if not missing:
        return
    fields = ", ".join(_format_field_name(field) for field in missing[:6])
    st.warning(
        tr("Fehlende Pflichtfelder:", "Missing mandatory fields:") + f" {fields}"
    )


def _render_salary_expectation(profile: Mapping[str, Any]) -> None:
    st.markdown(f"### 💰 {tr('Gehaltserwartung', 'Salary expectation')}")
    if st.button(
        tr("Gehaltserwartung aktualisieren", "Update salary expectation"),
        use_container_width=True,
        key="update_salary_expectation",
    ):
        with st.spinner(
            tr("Berechne neue Gehaltseinschätzung…", "Calculating salary estimate…")
        ):
            estimate_salary_expectation()

    estimate: Mapping[str, Any] | None = st.session_state.get(UIKeys.SALARY_ESTIMATE)
    explanation = st.session_state.get(UIKeys.SALARY_EXPLANATION)
    timestamp: str | None = st.session_state.get(UIKeys.SALARY_REFRESH)

    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            st.caption(
                tr("Zuletzt aktualisiert", "Last refreshed")
                + f": {dt.strftime('%d.%m.%Y %H:%M')}"
            )
        except ValueError:
            pass

    if not estimate:
        st.caption(
            tr(
                "Noch keine Schätzung vorhanden. Ergänze Jobtitel und Standort, um zu starten.",
                "No estimate yet. Provide job title and location to get started.",
            )
        )
        if isinstance(explanation, str) and explanation:
            st.caption(explanation)
        elif explanation and not isinstance(explanation, str):
            st.caption(str(explanation))
        return

    currency = estimate.get("currency") or profile.get("compensation", {}).get(
        "currency"
    )
    salary_min = estimate.get("salary_min")
    salary_max = estimate.get("salary_max")
    st.markdown(
        f"**{tr('Erwartete Spanne', 'Expected range')}**: "
        f"{_format_salary_range(salary_min, salary_max, currency)}"
    )

    user_comp = profile.get("compensation", {})
    user_min = user_comp.get("salary_min")
    user_max = user_comp.get("salary_max")
    user_currency = user_comp.get("currency") or currency

    if user_min or user_max:
        st.markdown(
            f"**{tr('Eingegebene Spanne', 'Entered range')}**: "
            f"{_format_salary_range(user_min, user_max, user_currency)}"
        )

    factor_rows = _prepare_salary_factor_rows(
        explanation,
        benchmark_currency=currency,
        user_currency=user_currency,
    )
    if factor_rows:
        st.markdown(_build_salary_factor_table(factor_rows))
    elif isinstance(explanation, str) and explanation:
        st.caption(explanation)
    elif explanation and not isinstance(explanation, str):
        st.caption(str(explanation))


def _format_field_name(path: str) -> str:
    """Return a human readable field name."""

    return path.replace("_", " ").replace(".", " → ").title()


def _format_salary_range(
    salary_min: Any, salary_max: Any, currency: str | None
) -> str:
    """Format a salary range for display."""

    currency = currency or ""
    if salary_min is None and salary_max is None:
        return tr("Keine Angaben", "No data")

    def _fmt(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{numeric:,.0f} {currency}".replace(",", "·") if currency else f"{numeric:,.0f}".replace(",", "·")

    if salary_min is not None and salary_max is not None:
        return f"{_fmt(salary_min)} – {_fmt(salary_max)}"
    value = salary_min if salary_min is not None else salary_max
    return _fmt(value)


def _prepare_salary_factor_rows(
    explanation: object,
    *,
    benchmark_currency: str | None,
    user_currency: str | None,
) -> list[tuple[str, str, str]]:
    """Normalize explanation data for rendering."""

    factors: list[Mapping[str, Any]] = []
    if isinstance(explanation, list):
        factors = [item for item in explanation if isinstance(item, Mapping)]
    elif isinstance(explanation, Mapping):
        candidate = explanation.get("factors") if "factors" in explanation else None
        if isinstance(candidate, list):
            factors = [item for item in candidate if isinstance(item, Mapping)]
        else:
            for key, value in explanation.items():
                if isinstance(value, Mapping):
                    item = dict(value)
                    item.setdefault("key", key)
                    factors.append(item)
                else:
                    factors.append({"key": key, "value": value, "impact": None})

    rows: list[tuple[str, str, str]] = []
    for factor in factors:
        key = str(factor.get("key", ""))
        label = _factor_label(key)
        value = _factor_value(key, factor.get("value"), benchmark_currency)
        impact = _factor_impact(
            factor.get("impact"),
            benchmark_currency,
            user_currency,
        )
        rows.append((label, value, impact))

    return rows


_FACTOR_LABELS: dict[str, tuple[str, str]] = {
    "source": ("Quelle", "Source"),
    "benchmark_role": ("Benchmark-Rolle", "Benchmark role"),
    "benchmark_country": ("Benchmark-Land", "Benchmark country"),
    "benchmark_range_raw": ("Rohbereich", "Raw range"),
    "currency": ("Währung", "Currency"),
    "salary_min": ("Unteres Benchmark-Ende", "Benchmark lower bound"),
    "salary_max": ("Oberes Benchmark-Ende", "Benchmark upper bound"),
    "summary": ("Zusammenfassung", "Summary"),
    "adjustments": ("Angewandte Anpassungen", "Applied adjustments"),
}


_IMPACT_NOTES: dict[str, tuple[str, str]] = {
    "fallback_source": (
        "Automatischer Fallback auf Benchmark-Daten",
        "Automatic fallback to benchmark data",
    ),
    "no_user_input": (
        "Keine Nutzereingabe zum Vergleich",
        "No user input to compare",
    ),
    "no_benchmark_value": (
        "Keine Benchmark-Werte verfügbar",
        "No benchmark values available",
    ),
    "currency_mismatch": (
        "Nutzereingabe in anderer Währung",
        "User input uses different currency",
    ),
}


def _factor_label(key: str) -> str:
    de, en = _FACTOR_LABELS.get(
        key,
        (key.replace("_", " ").replace(".", " → ").title(),) * 2,
    )
    return tr(de, en)


def _factor_value(key: str, value: Any, currency: str | None) -> str:
    if value is None or value == "":
        return tr("Keine Angaben", "No data")
    if key in {"salary_min", "salary_max"}:
        return _format_salary_value(value, currency)
    if isinstance(value, float):
        return f"{value:,.0f}".replace(",", "·")
    return str(value)


def _factor_impact(
    impact: Any,
    benchmark_currency: str | None,
    user_currency: str | None,
) -> str:
    if not impact:
        return tr("Keine Auswirkung berechnet", "No impact calculated")
    if not isinstance(impact, Mapping):
        return str(impact)

    parts: list[str] = []
    note = impact.get("note")
    if note:
        note_text = _IMPACT_NOTES.get(note)
        if note_text:
            parts.append(tr(*note_text))
        else:
            parts.append(str(note))

    absolute = impact.get("absolute")
    currency_to_use = impact.get("user_currency") or user_currency or benchmark_currency
    if isinstance(absolute, (int, float)) and not math.isnan(absolute):
        parts.append(_format_salary_value(absolute, currency_to_use, signed=True))

    relative = impact.get("relative")
    if isinstance(relative, (int, float)) and math.isfinite(relative):
        parts.append(f"({relative:+.1%})")

    user_value = impact.get("user_value")
    if user_value is not None:
        user_value_text = _format_salary_value(
            user_value,
            impact.get("user_currency") or user_currency or benchmark_currency,
        )
        parts.append(
            tr("vs. Eingabe {value}", "vs. input {value}").format(value=user_value_text)
        )

    filtered = [segment for segment in parts if segment]
    if not filtered:
        return tr("Keine Auswirkung berechnet", "No impact calculated")
    return " · ".join(filtered)


def _format_salary_value(value: Any, currency: str | None, *, signed: bool = False) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)

    fmt = f"{numeric:+,.0f}" if signed else f"{numeric:,.0f}"
    fmt = fmt.replace(",", "·")
    if currency:
        return f"{fmt} {currency}".strip()
    return fmt


def _build_salary_factor_table(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return ""
    header = (
        tr("Faktor", "Factor"),
        tr("Wert", "Value"),
        tr("Wirkung", "Impact"),
    )
    lines = [
        "| "
        + " | ".join(_escape_table(segment) for segment in header)
        + " |",
        "| --- | --- | --- |",
    ]
    for label, value, impact in rows:
        lines.append(
            "| "
            + " | ".join(_escape_table(segment) for segment in (label, value, impact))
            + " |"
        )
    return "\n".join(lines)


def _escape_table(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


__all__ = ["render_sidebar"]
