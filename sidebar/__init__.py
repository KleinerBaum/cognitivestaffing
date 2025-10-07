from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from core.preview import build_prefilled_sections, preview_value_to_text
from utils.i18n import tr

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

SECTION_BY_STEP: dict[int, int] = {1: 1, 2: 2, 3: 3}


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
        _render_hero(context.prefilled_sections)
        st.divider()
        _render_progress(context)
        _render_global_tips()
        _render_snapshot(context.prefilled_sections)
        _render_step_context(context)
        st.divider()
        _render_salary_expectation(context.profile)


def _ensure_ui_defaults() -> None:
    """Initialise language and theme toggles in session state."""

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")
    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]
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

    def _on_lang_change() -> None:
        st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    lang_options = {"de": "DE", "en": "EN"}

    st.markdown(f"### ⚙️ {tr('Einstellungen', 'Settings')}")
    st.toggle("Dark Mode 🌙", key="ui.dark_mode", on_change=_on_theme_toggle)
    st.radio(
        tr("Sprache", "Language"),
        options=list(lang_options.keys()),
        key=UIKeys.LANG_SELECT,
        horizontal=True,
        format_func=lambda key: lang_options[key],
        on_change=_on_lang_change,
    )


def _render_hero(prefilled_sections: list[tuple[str, list[tuple[str, Any]]]]) -> None:
    """Render hero card with quick headline info."""

    highlighted_paths = (
        "company.name",
        "position.job_title",
        "location.primary_city",
        "location.country",
    )
    preview_values: dict[str, str] = {}
    for _, entries in prefilled_sections:
        for path, value in entries:
            if path not in highlighted_paths:
                continue
            text_value = preview_value_to_text(value)
            if text_value and path not in preview_values:
                preview_values[path] = text_value

    hero_title = tr("Dein Recruiting-Co-Pilot", "Your recruiting co-pilot")
    hero_fallback_subtitle = tr(
        "Verwalte den Prozess Schritt für Schritt – alle Angaben bleiben erhalten.",
        "Manage the process step by step – your inputs stay safe.",
    )
    hero_lines: list[str] = []
    for path in ("company.name", "position.job_title"):
        text_value = preview_values.get(path)
        if text_value:
            hero_lines.append(html.escape(text_value))

    location_parts = [
        preview_values.get("location.primary_city"),
        preview_values.get("location.country"),
    ]
    location_text = ", ".join(part for part in location_parts if part)
    if location_text:
        hero_lines.append(html.escape(location_text))

    hero_subtitle_html = (
        "<br/>".join(hero_lines) if hero_lines else html.escape(hero_fallback_subtitle)
    )
    status_label = tr("Wizard-Status", "Wizard status")

    st.markdown(
        f"""
        <div class="sidebar-hero">
          <div class="sidebar-hero__icon">🧭</div>
          <div>
            <p class="sidebar-hero__eyebrow">{status_label}</p>
            <h2 class="sidebar-hero__title">{hero_title}</h2>
            <p class="sidebar-hero__subtitle">{hero_subtitle_html}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_progress(context: SidebarContext) -> None:
    """Display progress across wizard steps."""

    current = st.session_state.get(StateKeys.STEP, 0)
    st.markdown(f"### 📍 {tr('Fortschritt', 'Progress')}")

    st.markdown('<ul class="sidebar-stepper">', unsafe_allow_html=True)
    for idx, (_key, label) in enumerate(STEP_LABELS):
        status = _step_status(idx, current, context.missing_by_section)
        badge = _status_badge(status)
        note = _status_note(idx, context.missing_by_section)
        st.markdown(
            f"<li class='sidebar-step sidebar-step--{status}'>"
            f"{badge}<span class='sidebar-step__label'>{label}</span>"
            f"{note}</li>",
            unsafe_allow_html=True,
        )
    st.markdown("</ul>", unsafe_allow_html=True)


def _step_status(
    idx: int, current: int, missing_by_section: Mapping[int, list[str]]
) -> str:
    """Return visual status for a wizard step."""

    section = SECTION_BY_STEP.get(idx)
    has_missing = bool(section and missing_by_section.get(section))

    if idx == current:
        return "current"
    if idx < current:
        return "warning" if has_missing else "done"
    return "blocked" if has_missing else "upcoming"


def _status_badge(status: str) -> str:
    """Return emoji badge for step status."""

    badges = {
        "current": "<span class='sidebar-step__badge'>🟣</span>",
        "done": "<span class='sidebar-step__badge'>✅</span>",
        "warning": "<span class='sidebar-step__badge'>⚠️</span>",
        "blocked": "<span class='sidebar-step__badge'>⏳</span>",
        "upcoming": "<span class='sidebar-step__badge'>➡️</span>",
    }
    return badges.get(status, "")


def _status_note(idx: int, missing_by_section: Mapping[int, list[str]]) -> str:
    """Return HTML note for steps that miss critical fields."""

    section = SECTION_BY_STEP.get(idx)
    if not section:
        return ""
    missing = missing_by_section.get(section, [])
    if not missing:
        return ""
    count = len(missing)
    label = tr("fehlend", "missing")
    return f"<span class='sidebar-step__note'>{count} {label}</span>"


def _render_global_tips() -> None:
    """Show evergreen usage tips."""

    st.markdown(f"### 💡 {tr('Tipps', 'Tips')}")
    st.markdown(
        tr(
            "- Folge dem Wizard Schritt für Schritt – deine Eingaben bleiben erhalten.\n"
            "- KI-Ergebnisse findest du gesammelt in der Summary.",
            "- Work through the wizard step by step – your inputs remain persistent.\n"
            "- All AI-generated results are available on the summary step.",
        )
    )


def _render_snapshot(
    prefilled_sections: list[tuple[str, list[tuple[str, Any]]]]
) -> None:
    """Render quick snapshot of captured data."""

    st.markdown(f"### 🗂️ {tr('Schnellüberblick', 'Quick snapshot')}")
    if not prefilled_sections:
        st.caption(tr("Noch keine Angaben vorhanden.", "No entries captured yet."))
        return

    for label, entries in prefilled_sections:
        st.markdown(f"#### {label}")
        for path, value in entries[:5]:
            preview = preview_value_to_text(value)
            if not preview:
                continue
            st.markdown(f"- **{_format_field_name(path)}:** {preview}")


def _render_step_context(context: SidebarContext) -> None:
    """Render contextual guidance for the active wizard step."""

    current = st.session_state.get(StateKeys.STEP, 0)
    st.markdown(f"### 🧭 {tr('Kontext zum Schritt', 'Step context')}")

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
        st.caption(tr("Keine Kontextinformationen verfügbar.", "No context available."))
        return

    renderer(context)


def _render_onboarding_context(context: SidebarContext) -> None:
    method = st.session_state.get(UIKeys.INPUT_METHOD, "text")
    method_labels = {
        "text": tr("Textanalyse aktiv", "Text ingestion active"),
        "file": tr("Dateiupload aktiv", "File upload active"),
        "url": tr("URL-Import aktiv", "URL ingestion active"),
    }
    st.markdown(f"#### {tr('Aktuelle Quelle', 'Current source')}")
    st.caption(method_labels.get(method, method))

    summary = context.extraction_summary
    st.markdown(f"#### {tr('Erste Extraktion', 'Initial extraction')}")
    if summary:
        for label, value in summary.items():
            st.markdown(f"- **{label}:** {value}")
    else:
        st.caption(
            tr(
                "Sobald du Daten importierst, erscheinen hier die wichtigsten Ergebnisse.",
                "As soon as you import data the top findings will appear here.",
            )
        )

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
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        total_tok = in_tok + out_tok
        st.caption(
            tr("Tokenverbrauch", "Token usage")
            + f": {in_tok} + {out_tok} = {total_tok}"
        )


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
    explanation: str | None = st.session_state.get(UIKeys.SALARY_EXPLANATION)
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
        if explanation:
            st.caption(explanation)
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
        deltas = _format_salary_delta(
            salary_min, salary_max, user_min, user_max, user_currency
        )
        if deltas:
            st.caption(deltas)

    if explanation:
        st.caption(explanation)


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


def _format_salary_delta(
    est_min: Any,
    est_max: Any,
    user_min: Any,
    user_max: Any,
    currency: str | None,
) -> str:
    """Return textual delta between estimated and entered salary."""

    try:
        est_min_f = float(est_min) if est_min is not None else None
        est_max_f = float(est_max) if est_max is not None else None
        user_min_f = float(user_min) if user_min is not None else None
        user_max_f = float(user_max) if user_max is not None else None
    except (TypeError, ValueError):
        return ""

    parts: list[str] = []
    currency = currency or ""
    if est_min_f is not None and user_min_f is not None:
        diff_min = user_min_f - est_min_f
        if abs(diff_min) >= 500:
            parts.append(
                tr("Min-Abweichung", "Min delta")
                + f": {diff_min:+,.0f} {currency}".replace(",", "·")
            )
    if est_max_f is not None and user_max_f is not None:
        diff_max = user_max_f - est_max_f
        if abs(diff_max) >= 500:
            parts.append(
                tr("Max-Abweichung", "Max delta")
                + f": {diff_max:+,.0f} {currency}".replace(",", "·")
            )
    return " · ".join(parts)


__all__ = ["render_sidebar"]
