from __future__ import annotations

from datetime import date
from types import ModuleType
from typing import Any, Mapping, cast

import streamlit as st

from components import widget_factory
from components.form_fields import text_input_with_state
from constants.keys import ProfilePaths
from wizard.layout import (
    format_missing_label,
    merge_missing_help,
    render_section_heading,
    render_step_warning_banner,
)
from wizard.step_layout import render_step_layout
from wizard_router import WizardContext
from utils.i18n import tr
from wizard.sections.team_advisor import (
    render_team_advisor,
    render_team_advisor_unavailable_notice,
)

__all__ = ["step_team"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "CONTINENT_COUNTRIES",
    "CUSTOMER_CONTACT_TOGGLE_LABEL",
    "EMPLOYMENT_OVERTIME_TOGGLE_HELP",
    "EMPLOYMENT_RELOCATION_TOGGLE_HELP",
    "EMPLOYMENT_SECURITY_TOGGLE_HELP",
    "EMPLOYMENT_SHIFT_TOGGLE_HELP",
    "EMPLOYMENT_TRAVEL_TOGGLE_HELP",
    "EMPLOYMENT_VISA_TOGGLE_HELP",
    "EUROPEAN_COUNTRIES",
    "GERMAN_STATES",
    "POSITION_CUSTOMER_CONTACT_DETAILS_HINT",
    "POSITION_CUSTOMER_CONTACT_TOGGLE_HELP",
    "REQUIRED_SUFFIX",
    "ROLE_SUMMARY_LABEL",
    "_apply_field_lock_kwargs",
    "_default_date",
    "_field_lock_config",
    "_get_profile_state",
    "_missing_fields_for_section",
    "_render_esco_occupation_selector",
    "_render_followups_for_fields",
    "_render_followups_for_step",
    "_render_target_start_date_input",
    "_resolve_step_copy",
    "_string_or_empty",
    "_update_profile",
)

CONTINENT_COUNTRIES: Any = cast(Any, None)
CUSTOMER_CONTACT_TOGGLE_LABEL: Any = cast(Any, None)
EMPLOYMENT_OVERTIME_TOGGLE_HELP: Any = cast(Any, None)
EMPLOYMENT_RELOCATION_TOGGLE_HELP: Any = cast(Any, None)
EMPLOYMENT_SECURITY_TOGGLE_HELP: Any = cast(Any, None)
EMPLOYMENT_SHIFT_TOGGLE_HELP: Any = cast(Any, None)
EMPLOYMENT_TRAVEL_TOGGLE_HELP: Any = cast(Any, None)
EMPLOYMENT_VISA_TOGGLE_HELP: Any = cast(Any, None)
EUROPEAN_COUNTRIES: Any = cast(Any, None)
GERMAN_STATES: Any = cast(Any, None)
POSITION_CUSTOMER_CONTACT_DETAILS_HINT: Any = cast(Any, None)
POSITION_CUSTOMER_CONTACT_TOGGLE_HELP: Any = cast(Any, None)
REQUIRED_SUFFIX: Any = cast(Any, None)
ROLE_SUMMARY_LABEL: Any = cast(Any, None)
_apply_field_lock_kwargs: Any = cast(Any, None)
_default_date: Any = cast(Any, None)
_field_lock_config: Any = cast(Any, None)
_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_esco_occupation_selector: Any = cast(Any, None)
_render_followups_for_fields: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_target_start_date_input: Any = cast(Any, None)
_resolve_step_copy: Any = cast(Any, None)
_string_or_empty: Any = cast(Any, None)
_update_profile: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _format_summary_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(cleaned)
    return str(value).strip()


def _render_team_summary(profile: Mapping[str, Any]) -> None:
    lang = st.session_state.get("lang", "de")
    department = profile.get("department") if isinstance(profile.get("department"), dict) else {}
    team = profile.get("team") if isinstance(profile.get("team"), dict) else {}
    position = profile.get("position") if isinstance(profile.get("position"), dict) else {}
    meta = profile.get("meta") if isinstance(profile.get("meta"), dict) else {}
    items = [
        (tr("Jobtitel", "Job title", lang=lang), position.get("job_title")),
        (tr("Abteilung", "Department", lang=lang), department.get("name")),
        (tr("Teamname", "Team name", lang=lang), team.get("name")),
        (tr("Berichtslinie", "Reporting line", lang=lang), team.get("reporting_line")),
        (tr("Vorgesetzte Person", "Reporting manager", lang=lang), position.get("reporting_manager_name")),
        (tr("Startdatum", "Start date", lang=lang), meta.get("target_start_date")),
    ]
    summary_lines = []
    for label, value in items:
        formatted = _format_summary_value(value)
        if formatted:
            summary_lines.append(f"- **{label}**: {formatted}")
    if summary_lines:
        st.markdown("\n".join(summary_lines))
    else:
        st.info(tr("Noch keine Teamdetails vorhanden.", "No team details captured yet.", lang=lang))


def _step_team() -> None:
    """Render the team and position context step.

    Returns:
        None
    """

    profile = _get_profile_state()
    missing_here = _missing_fields_for_section(2)
    title, subtitle, intros = _resolve_step_copy("team", profile)
    data = profile
    data.setdefault("company", {})
    position = data.setdefault("position", {})
    team = data.setdefault("team", {})
    data.setdefault("location", {})
    meta_data = data.setdefault("meta", {})
    employment = data.setdefault("employment", {})

    def _render_team_tools() -> None:
        render_team_advisor_unavailable_notice(st.session_state.get("lang", "de"))
        render_team_advisor(profile=data, position=position, update_profile=_update_profile)

    def _render_team_missing() -> None:
        _render_team_inputs()
        _render_followups_for_fields((ProfilePaths.POSITION_JOB_TITLE,), data, container_factory=st.container)
        _render_followups_for_fields((ProfilePaths.META_TARGET_START_DATE,), data, container_factory=st.container)
        _render_followups_for_fields((ProfilePaths.POSITION_REPORTS_TO,), data, container_factory=st.container)
        _render_followups_for_fields(
            (ProfilePaths.POSITION_REPORTING_MANAGER_NAME,), data, container_factory=st.container
        )
        _render_followups_for_fields((ProfilePaths.POSITION_ROLE_SUMMARY,), data, container_factory=st.container)
        _render_followups_for_step("team", data)

    def _render_team_inputs() -> None:
        render_step_warning_banner()
        render_section_heading(
            tr("Pflichtangaben", "Required basics"),
            icon="📌",
            size="compact",
        )
        required_block = st.container()

        with required_block:
            job_title_container = st.container()
            title_label = format_missing_label(
                tr("Jobtitel", "Job title") + REQUIRED_SUFFIX,
                field_path=ProfilePaths.POSITION_JOB_TITLE,
                missing_fields=missing_here,
            )
            title_lock = _field_lock_config(
                ProfilePaths.POSITION_JOB_TITLE,
                title_label,
                container=job_title_container,
                context="step",
            )
            job_title_kwargs = _apply_field_lock_kwargs(
                title_lock,
                {
                    "help": merge_missing_help(
                        None,
                        field_path=ProfilePaths.POSITION_JOB_TITLE,
                        missing_fields=missing_here,
                    )
                },
            )
            position["job_title"] = widget_factory.text_input(
                ProfilePaths.POSITION_JOB_TITLE,
                title_lock["label"],
                widget_factory=job_title_container.text_input,
                placeholder=tr("Jobtitel eingeben", "Enter the job title"),
                value_formatter=_string_or_empty,
                **job_title_kwargs,
            )
            _update_profile(ProfilePaths.POSITION_JOB_TITLE, position["job_title"])
            if ProfilePaths.POSITION_JOB_TITLE in missing_here and not position.get("job_title"):
                job_title_container.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

            reporting_container = st.container()
            reporting_label = format_missing_label(
                tr("Berichtslinie (Funktion)", "Reporting line (function)") + REQUIRED_SUFFIX,
                field_path=ProfilePaths.TEAM_REPORTING_LINE,
                missing_fields=missing_here,
            )
            team["reporting_line"] = widget_factory.text_input(
                ProfilePaths.TEAM_REPORTING_LINE,
                reporting_label,
                widget_factory=reporting_container.text_input,
                placeholder=tr("Zugeordnete Leitung eintragen", "Enter the overseeing function"),
                value_formatter=_string_or_empty,
                help=merge_missing_help(
                    None,
                    field_path=ProfilePaths.TEAM_REPORTING_LINE,
                    missing_fields=missing_here,
                ),
            )
            _update_profile(ProfilePaths.TEAM_REPORTING_LINE, team.get("reporting_line", ""))
            _update_profile(ProfilePaths.POSITION_REPORTING_LINE, team.get("reporting_line", ""))
            if ProfilePaths.TEAM_REPORTING_LINE in missing_here and not team.get("reporting_line"):
                reporting_container.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

            start_container = st.container()
            start_selection = _render_target_start_date_input(start_container, meta_data, missing_fields=missing_here)
            meta_data["target_start_date"] = start_selection.isoformat() if isinstance(start_selection, date) else ""

        render_section_heading(tr("Team & Struktur", "Team & Structure"))
        role_cols = st.columns((1.3, 1))
        with role_cols[0]:
            _render_esco_occupation_selector(position)

        position["seniority_level"] = widget_factory.text_input(
            ProfilePaths.POSITION_SENIORITY,
            tr("Seniorität", "Seniority"),
            widget_factory=role_cols[1].text_input,
            placeholder=tr("Karrierestufe angeben", "Enter the seniority level"),
            value_formatter=_string_or_empty,
        )

        reports_to_container = st.container()
        reports_to_label = tr("Berichtet an (Funktion)", "Reports to (title)")
        position["reports_to"] = widget_factory.text_input(
            ProfilePaths.POSITION_REPORTS_TO,
            reports_to_label,
            widget_factory=reports_to_container.text_input,
            placeholder=tr("Führungstitel eintragen", "Enter the manager title"),
            value_formatter=_string_or_empty,
        )
        _update_profile(ProfilePaths.POSITION_REPORTS_TO, position.get("reports_to", ""))

        manager_cols = st.columns((1, 1))
        position["reporting_manager_name"] = widget_factory.text_input(
            ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
            format_missing_label(
                tr("Vorgesetzte Person", "Reporting manager") + REQUIRED_SUFFIX,
                field_path=ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
                missing_fields=missing_here,
            ),
            widget_factory=manager_cols[0].text_input,
            placeholder=tr(
                "Name der vorgesetzten Person eintragen",
                "Enter the reporting manager's name",
            ),
            value_formatter=_string_or_empty,
            help=merge_missing_help(
                None,
                field_path=ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
                missing_fields=missing_here,
            ),
        )
        _update_profile(
            ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
            position.get("reporting_manager_name", ""),
        )
        position["customer_contact_required"] = manager_cols[1].toggle(
            tr(*CUSTOMER_CONTACT_TOGGLE_LABEL),
            value=bool(position.get("customer_contact_required")),
            help=tr(*POSITION_CUSTOMER_CONTACT_TOGGLE_HELP),
        )
        _update_profile(
            ProfilePaths.POSITION_CUSTOMER_CONTACT_REQUIRED,
            position.get("customer_contact_required"),
        )
        if position.get("customer_contact_required"):
            position["customer_contact_details"] = st.text_area(
                tr("Kontakt-Details", "Contact details"),
                value=position.get("customer_contact_details", ""),
                key=ProfilePaths.POSITION_CUSTOMER_CONTACT_DETAILS,
                height=80,
                placeholder=tr(*POSITION_CUSTOMER_CONTACT_DETAILS_HINT),
            )
        else:
            position.pop("customer_contact_details", None)
        _update_profile(
            ProfilePaths.POSITION_CUSTOMER_CONTACT_DETAILS,
            position.get("customer_contact_details"),
        )
        summary_container = st.container()
        summary_label = format_missing_label(
            tr(*ROLE_SUMMARY_LABEL),
            field_path=ProfilePaths.POSITION_ROLE_SUMMARY,
            missing_fields=missing_here,
        )
        if ProfilePaths.POSITION_ROLE_SUMMARY in missing_here:
            summary_label += REQUIRED_SUFFIX
        position["role_summary"] = summary_container.text_area(
            summary_label,
            value=st.session_state.get(ProfilePaths.POSITION_ROLE_SUMMARY, position.get("role_summary", "")),
            height=120,
            key=ProfilePaths.POSITION_ROLE_SUMMARY,
            help=merge_missing_help(
                None,
                field_path=ProfilePaths.POSITION_ROLE_SUMMARY,
                missing_fields=missing_here,
            ),
        )
        if ProfilePaths.POSITION_ROLE_SUMMARY in missing_here and not position.get("role_summary"):
            summary_container.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

        render_section_heading(tr("Abteilung & Team", "Department & team"), icon="👥", size="compact")

        department = data.setdefault("department", {})
        dept_cols = st.columns(2, gap="small")
        department["name"] = dept_cols[0].text_input(
            tr("Abteilung", "Department"),
            value=department.get("name", ""),
            key=ProfilePaths.DEPARTMENT_NAME,
            placeholder=tr("Abteilung beschreiben", "Describe the department"),
        )
        _update_profile(ProfilePaths.DEPARTMENT_NAME, department.get("name", ""))
        department["function"] = dept_cols[1].text_input(
            tr("Funktion", "Function"),
            value=department.get("function", ""),
            key=ProfilePaths.DEPARTMENT_FUNCTION,
            placeholder=tr("Aufgabe des Bereichs skizzieren", "Outline the department's function"),
        )
        _update_profile(ProfilePaths.DEPARTMENT_FUNCTION, department.get("function", ""))

        leader_cols = st.columns(2, gap="small")
        department["leader_name"] = leader_cols[0].text_input(
            tr("Abteilungsleitung", "Department lead"),
            value=department.get("leader_name", ""),
            key=ProfilePaths.DEPARTMENT_LEADER_NAME,
            placeholder=tr("Name der Leitung", "Name of the lead"),
        )
        _update_profile(ProfilePaths.DEPARTMENT_LEADER_NAME, department.get("leader_name", ""))
        department["leader_title"] = leader_cols[1].text_input(
            tr("Titel der Leitung", "Lead title"),
            value=department.get("leader_title", ""),
            key=ProfilePaths.DEPARTMENT_LEADER_TITLE,
            placeholder=tr("Rollenbezeichnung der Leitung", "Lead's title"),
        )
        _update_profile(ProfilePaths.DEPARTMENT_LEADER_TITLE, department.get("leader_title", ""))

        department["strategic_goals"] = st.text_area(
            tr("Strategische Ziele", "Strategic goals"),
            value=department.get("strategic_goals", ""),
            key=ProfilePaths.DEPARTMENT_STRATEGIC_GOALS,
            height=90,
        )
        _update_profile(ProfilePaths.DEPARTMENT_STRATEGIC_GOALS, department.get("strategic_goals", ""))

        team_cols = st.columns((1, 1), gap="small")
        team["name"] = team_cols[0].text_input(
            tr("Teamname", "Team name"),
            value=team.get("name", ""),
            key=ProfilePaths.TEAM_NAME,
            placeholder=tr("Team benennen", "Name the team"),
        )
        _update_profile(ProfilePaths.TEAM_NAME, team.get("name", ""))
        team["mission"] = team_cols[1].text_input(
            tr("Teamauftrag", "Team mission"),
            value=team.get("mission", ""),
            key=ProfilePaths.TEAM_MISSION,
            placeholder=tr("Mission oder Zweck", "Mission or purpose"),
        )
        _update_profile(ProfilePaths.TEAM_MISSION, team.get("mission", ""))

        team_headcount_cols = st.columns(2, gap="small")
        team["headcount_current"] = team_headcount_cols[0].number_input(
            tr("Headcount aktuell", "Current headcount"),
            min_value=0,
            step=1,
            value=int(team.get("headcount_current") or 0),
            key=ProfilePaths.TEAM_HEADCOUNT_CURRENT,
        )
        _update_profile(ProfilePaths.TEAM_HEADCOUNT_CURRENT, team.get("headcount_current"))
        team["headcount_target"] = team_headcount_cols[1].number_input(
            tr("Headcount Ziel", "Target headcount"),
            min_value=0,
            step=1,
            value=int(team.get("headcount_target") or 0),
            key=ProfilePaths.TEAM_HEADCOUNT_TARGET,
        )
        _update_profile(ProfilePaths.TEAM_HEADCOUNT_TARGET, team.get("headcount_target"))

        team_details_cols = st.columns(2, gap="small")
        team["collaboration_tools"] = team_details_cols[0].text_input(
            tr("Tools", "Collaboration tools"),
            value=team.get("collaboration_tools", ""),
            key=ProfilePaths.TEAM_COLLABORATION_TOOLS,
            placeholder=tr("Genutzte Tools", "Tools in use"),
        )
        _update_profile(ProfilePaths.TEAM_COLLABORATION_TOOLS, team.get("collaboration_tools", ""))
        team["locations"] = team_details_cols[1].text_input(
            tr("Team-Standorte", "Team locations"),
            value=team.get("locations", ""),
            key=ProfilePaths.TEAM_LOCATIONS,
            placeholder=tr("Verteilte Standorte", "Distributed locations"),
        )
        _update_profile(ProfilePaths.TEAM_LOCATIONS, team.get("locations", ""))

        position["team_structure"] = st.text_input(
            tr("Teamstruktur", "Team structure"),
            value=position.get("team_structure", ""),
            key=ProfilePaths.POSITION_TEAM_STRUCTURE,
            placeholder=tr("Teamstruktur erläutern", "Explain the team structure"),
        )

        position["key_projects"] = st.text_area(
            tr("Schlüsselprojekte", "Key projects"),
            value=position.get("key_projects", ""),
            height=90,
        )

        render_section_heading(tr("Zeitplan", "Timing"), icon="⏱️", size="compact")

        timing_cols = st.columns((1.4, 1))
        application_deadline_default = _default_date(meta_data.get("application_deadline"))
        deadline_selection = timing_cols[0].date_input(
            tr("Bewerbungsschluss", "Application deadline"),
            value=application_deadline_default,
            format="YYYY-MM-DD",
        )
        meta_data["application_deadline"] = (
            deadline_selection.isoformat() if isinstance(deadline_selection, date) else ""
        )

        position["supervises"] = timing_cols[1].number_input(
            tr("Anzahl unterstellter Mitarbeiter", "Direct reports"),
            min_value=0,
            value=position.get("supervises", 0),
            step=1,
        )

        with st.expander(tr("Weitere Rollen-Details", "Additional role details")):
            position["performance_indicators"] = st.text_area(
                tr("Leistungskennzahlen", "Performance indicators"),
                value=position.get("performance_indicators", ""),
                height=80,
            )
            position["decision_authority"] = st.text_area(
                tr("Entscheidungsbefugnisse", "Decision-making authority"),
                value=position.get("decision_authority", ""),
                height=80,
            )

        render_section_heading(
            tr("Beschäftigung & Arbeitsmodell", "Employment & working model"),
            icon="🧭",
        )

        job_type_options = {
            "full_time": tr("Vollzeit", "Full-time"),
            "part_time": tr("Teilzeit", "Part-time"),
            "contract": tr("Freelance / Contract", "Contract"),
            "internship": tr("Praktikum", "Internship"),
            "working_student": tr("Werkstudent:in", "Working student"),
            "trainee_program": tr("Traineeprogramm", "Trainee program"),
            "apprenticeship": tr("Ausbildung", "Apprenticeship"),
            "temporary": tr("Befristet", "Temporary"),
            "other": tr("Sonstiges", "Other"),
        }
        contract_options = {
            "permanent": tr("Unbefristet", "Permanent"),
            "fixed_term": tr("Befristet", "Fixed term"),
            "contract": tr("Werkvertrag", "Contract"),
            "other": tr("Sonstiges", "Other"),
        }
        policy_options = {
            "onsite": tr("Vor Ort", "Onsite"),
            "hybrid": tr("Hybrid", "Hybrid"),
            "remote": tr("Remote", "Remote"),
        }

        job_cols = st.columns(3)
        job_keys = list(job_type_options.keys())
        job_default = employment.get("job_type", job_keys[0])
        job_index = job_keys.index(job_default) if job_default in job_keys else 0
        employment["job_type"] = job_cols[0].selectbox(
            tr("Beschäftigungsart", "Employment type"),
            options=job_keys,
            index=job_index,
            format_func=lambda key: job_type_options[key],
        )

        contract_keys = list(contract_options.keys())
        contract_default = employment.get("contract_type", contract_keys[0])
        contract_index = contract_keys.index(contract_default) if contract_default in contract_keys else 0
        employment["contract_type"] = job_cols[1].selectbox(
            tr("Vertragsform", "Contract type"),
            options=contract_keys,
            index=contract_index,
            format_func=lambda key: contract_options[key],
        )

        policy_keys = list(policy_options.keys())
        policy_default = employment.get("work_policy", policy_keys[0])
        policy_index = policy_keys.index(policy_default) if policy_default in policy_keys else 0
        employment["work_policy"] = job_cols[2].selectbox(
            tr("Arbeitsmodell", "Work policy"),
            options=policy_keys,
            index=policy_index,
            format_func=lambda key: policy_options[key],
        )

        schedule_options = {
            "standard": tr("Standard", "Standard"),
            "flexitime": tr("Gleitzeit", "Flexitime"),
            "shift": tr("Schichtarbeit", "Shift work"),
            "weekend": tr("Wochenendarbeit", "Weekend work"),
            "other": tr("Sonstiges", "Other"),
        }
        schedule_keys = list(schedule_options.keys())
        stored_schedule = str(employment.get("work_schedule") or "").strip()
        custom_schedule_value = ""
        if stored_schedule and stored_schedule not in schedule_keys:
            custom_schedule_value = stored_schedule
            schedule_default = "other"
        else:
            schedule_default = stored_schedule or schedule_keys[0]
        schedule_index = schedule_keys.index(schedule_default) if schedule_default in schedule_keys else 0

        st.divider()
        schedule_container = st.container()
        schedule_cols = schedule_container.columns((2, 1, 1))
        schedule_selection = schedule_cols[0].selectbox(
            tr("Arbeitszeitmodell", "Work schedule"),
            options=schedule_keys,
            index=schedule_index,
            format_func=lambda key: schedule_options[key],
        )
        if schedule_selection == "other":
            custom_value = (
                schedule_cols[0]
                .text_input(
                    tr("Individuelles Modell", "Custom schedule"),
                    value=custom_schedule_value,
                    placeholder=tr(
                        "Arbeitszeitmodell beschreiben",
                        "Describe the working time model",
                    ),
                )
                .strip()
            )
            employment["work_schedule"] = custom_value
        else:
            employment["work_schedule"] = schedule_selection

        remote_col = schedule_cols[1]
        if employment.get("work_policy") in {"hybrid", "remote"}:
            employment["remote_percentage"] = remote_col.number_input(
                tr("Remote-Anteil (%)", "Remote share (%)"),
                min_value=0,
                max_value=100,
                value=int(employment.get("remote_percentage") or 0),
            )
        else:
            remote_col.empty()
            employment.pop("remote_percentage", None)

        contract_end_col = schedule_cols[2]
        if employment.get("contract_type") == "fixed_term":
            contract_end_default = _default_date(employment.get("contract_end"), fallback=date.today())
            contract_end_value = contract_end_col.date_input(
                tr("Vertragsende", "Contract end"),
                value=contract_end_default,
                format="YYYY-MM-DD",
            )
            employment["contract_end"] = (
                contract_end_value.isoformat()
                if isinstance(contract_end_value, date)
                else employment.get("contract_end", "")
            )
        else:
            contract_end_col.empty()
            employment.pop("contract_end", None)

        toggle_row_1 = st.columns(3)
        employment["travel_required"] = toggle_row_1[0].toggle(
            tr("Reisetätigkeit?", "Travel required?"),
            value=bool(employment.get("travel_required")),
            help=tr(*EMPLOYMENT_TRAVEL_TOGGLE_HELP),
        )
        employment["relocation_support"] = toggle_row_1[1].toggle(
            tr("Relocation?", "Relocation?"),
            value=bool(employment.get("relocation_support")),
            help=tr(*EMPLOYMENT_RELOCATION_TOGGLE_HELP),
        )
        employment["visa_sponsorship"] = toggle_row_1[2].toggle(
            tr("Visum-Sponsoring?", "Visa sponsorship?"),
            value=bool(employment.get("visa_sponsorship")),
            help=tr(*EMPLOYMENT_VISA_TOGGLE_HELP),
        )

        toggle_row_2 = st.columns(3)
        employment["overtime_expected"] = toggle_row_2[0].toggle(
            tr("Überstunden?", "Overtime expected?"),
            value=bool(employment.get("overtime_expected")),
            help=tr(*EMPLOYMENT_OVERTIME_TOGGLE_HELP),
        )
        employment["security_clearance_required"] = toggle_row_2[1].toggle(
            tr("Sicherheitsüberprüfung?", "Security clearance required?"),
            value=bool(employment.get("security_clearance_required")),
            help=tr(*EMPLOYMENT_SECURITY_TOGGLE_HELP),
        )
        employment["shift_work"] = toggle_row_2[2].toggle(
            tr("Schichtarbeit?", "Shift work?"),
            value=bool(employment.get("shift_work")),
            help=tr(*EMPLOYMENT_SHIFT_TOGGLE_HELP),
        )

        if employment.get("travel_required"):
            with st.expander(tr("Details zur Reisetätigkeit", "Travel details"), expanded=True):
                col_share, col_region, col_details = st.columns((1, 2, 2))
                share_default = int(employment.get("travel_share") or 0)
                employment["travel_share"] = col_share.number_input(
                    tr("Reiseanteil (%)", "Travel share (%)"),
                    min_value=0,
                    max_value=100,
                    step=5,
                    value=share_default,
                )

                scope_options = [
                    ("germany", tr("Deutschland", "Germany")),
                    ("europe", tr("Europa", "Europe")),
                    ("worldwide", tr("Weltweit", "Worldwide")),
                ]
                scope_lookup = {value: label for value, label in scope_options}
                current_scope = employment.get("travel_region_scope", "germany")
                scope_index = next(
                    (idx for idx, (value, _) in enumerate(scope_options) if value == current_scope),
                    0,
                )
                selected_scope = col_region.selectbox(
                    tr("Reiseregion", "Travel region"),
                    options=[value for value, _ in scope_options],
                    format_func=lambda opt: scope_lookup[opt],
                    index=scope_index,
                )
                employment["travel_region_scope"] = selected_scope

                stored_regions = employment.get("travel_regions", [])
                stored_continents = employment.get("travel_continents", [])

                if selected_scope == "germany":
                    selected_regions = col_region.multiselect(
                        tr("Bundesländer", "Federal states"),
                        options=GERMAN_STATES,
                        default=[region for region in stored_regions if region in GERMAN_STATES],
                    )
                    employment["travel_regions"] = selected_regions
                    employment.pop("travel_continents", None)
                elif selected_scope == "europe":
                    selected_regions = col_region.multiselect(
                        tr("Länder (Europa)", "Countries (Europe)"),
                        options=EUROPEAN_COUNTRIES,
                        default=[region for region in stored_regions if region in EUROPEAN_COUNTRIES],
                    )
                    employment["travel_regions"] = selected_regions
                    employment.pop("travel_continents", None)
                else:
                    continent_options = list(CONTINENT_COUNTRIES.keys())
                    selected_continents = col_region.multiselect(
                        tr("Kontinente", "Continents"),
                        options=continent_options,
                        default=[continent for continent in stored_continents if continent in continent_options],
                    )
                    employment["travel_continents"] = selected_continents
                    base_continents = selected_continents or continent_options
                    available_countries = sorted(
                        {country for continent in base_continents for country in CONTINENT_COUNTRIES.get(continent, [])}
                    )
                    selected_countries = col_region.multiselect(
                        tr("Länder", "Countries"),
                        options=available_countries,
                        default=[country for country in stored_regions if country in available_countries],
                    )
                    employment["travel_regions"] = selected_countries

                employment["travel_details"] = text_input_with_state(
                    tr("Zusatzinfos", "Additional details"),
                    target=employment,
                    field="travel_details",
                    widget_factory=col_details.text_input,
                )
        else:
            for field_name in (
                "travel_share",
                "travel_region_scope",
                "travel_regions",
                "travel_continents",
                "travel_details",
            ):
                employment.pop(field_name, None)

        if employment.get("relocation_support"):
            employment["relocation_details"] = text_input_with_state(
                tr("Relocation-Details", "Relocation details"),
                target=employment,
                field="relocation_details",
            )
        else:
            employment.pop("relocation_details", None)

    def _render_team_known() -> None:
        render_step_warning_banner()
        for intro in intros:
            st.caption(intro)
        _render_team_summary(profile)

    # GREP:STEP_TEAM_LAYOUT_V1
    render_step_layout(
        title,
        subtitle,
        known_cb=_render_team_known,
        missing_cb=_render_team_missing,
        missing_paths=missing_here,
        tools_cb=_render_team_tools,
    )


def step_team(context: WizardContext) -> None:
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_team()
