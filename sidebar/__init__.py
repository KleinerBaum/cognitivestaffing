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
        _render_hero(context)
        st.divider()
        _render_progress(context)
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


def _render_onboarding_context(context: SidebarContext) -> None:
    step_order, step_entries = _build_initial_extraction_entries(context)
    if not any(step_entries.values()):
        st.caption(
            tr(
                "Sobald du Daten importierst, erscheinen hier die wichtigsten Ergebnisse.",
                "As soon as you import data the top findings will appear here.",
            )
        )
        return

    select_key = "ui.initial_extraction_step"
    if (
        select_key not in st.session_state
        or st.session_state[select_key] not in step_order
    ):
        default_step = next(
            (key for key in step_order if step_entries.get(key)),
            step_order[0],
        )
        st.session_state[select_key] = default_step

    step_label_map = dict(STEP_LABELS)
    selected_step = st.selectbox(
        tr("Schritt auswählen", "Select step"),
        options=step_order,
        key=select_key,
        format_func=lambda key: step_label_map.get(key, key.title()),
    )

    entries = step_entries.get(selected_step, [])
    if entries:
        for label, value in entries:
            st.markdown(f"- **{label}:** {value}")
    else:
        st.caption(
            tr(
                "Für diesen Schritt liegen noch keine Daten vor.",
                "No data captured for this step yet.",
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
