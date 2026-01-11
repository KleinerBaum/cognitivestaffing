from __future__ import annotations

from types import ModuleType
from typing import Any, Mapping, cast

import streamlit as st

from components import widget_factory
from constants.keys import ProfilePaths
from utils.i18n import tr
from wizard.layout import (
    format_missing_label,
    merge_missing_help,
    render_missing_field_summary,
    render_section_heading,
    render_step_warning_banner,
)
from wizard.step_layout import render_step_layout
from wizard.business_context import (
    domain_suggestion_chips,
    suggest_esco_or_industry_codes,
)

__all__ = ["step_business_context"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "COMPACT_STEP_STYLE",
    "REQUIRED_SUFFIX",
    "_get_profile_state",
    "_missing_fields_for_section",
    "_resolve_step_copy",
    "_update_profile",
    "_render_followups_for_step",
)

COMPACT_STEP_STYLE: Any = cast(Any, None)
REQUIRED_SUFFIX: Any = cast(Any, None)
_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_resolve_step_copy: Any = cast(Any, None)
_update_profile: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _render_confidence_badge(source_confidence: Mapping[str, str], field_key: str) -> None:
    badge = source_confidence.get(field_key)
    if not badge:
        return
    st.caption(tr("Quelle", "Source") + f": {badge}")


def _ensure_badge(source_confidence: dict[str, str], field_key: str, badge: str) -> None:
    if field_key not in source_confidence:
        source_confidence[field_key] = badge


def _step_business_context() -> None:
    st.markdown(COMPACT_STEP_STYLE, unsafe_allow_html=True)

    profile = _get_profile_state()
    missing_here = _missing_fields_for_section(1)
    title, subtitle, intros = _resolve_step_copy("company", profile)

    data = profile
    business_context = data.setdefault("business_context", {})
    source_confidence = business_context.setdefault("source_confidence", {})
    if not isinstance(source_confidence, dict):
        source_confidence = dict(source_confidence or {})
        business_context["source_confidence"] = source_confidence

    def _render_business_context_missing() -> None:
        _render_followups_for_step("company", data)

    def _render_business_context_known() -> None:
        render_step_warning_banner()
        render_missing_field_summary(missing_here)
        if subtitle:
            st.caption(subtitle)
        for intro in intros:
            st.caption(intro)

        render_section_heading(
            tr("Business-Domain", "Business domain"),
            icon="🧭",
            size="compact",
        )

        domain_container = st.container()
        domain_label = format_missing_label(
            tr("Business-Domain", "Business domain") + REQUIRED_SUFFIX,
            field_path=ProfilePaths.BUSINESS_CONTEXT_DOMAIN,
            missing_fields=missing_here,
        )
        domain_value = widget_factory.text_input(
            ProfilePaths.BUSINESS_CONTEXT_DOMAIN,
            domain_label,
            widget_factory=domain_container.text_input,
            placeholder=tr("z. B. SaaS für FinTech", "e.g. SaaS for fintech"),
            value_formatter=lambda value: str(value or ""),
            help=merge_missing_help(
                None,
                field_path=ProfilePaths.BUSINESS_CONTEXT_DOMAIN,
                missing_fields=missing_here,
            ),
        )
        business_context["domain"] = domain_value
        _update_profile(ProfilePaths.BUSINESS_CONTEXT_DOMAIN, domain_value)
        if domain_value and not source_confidence.get("domain"):
            _ensure_badge(source_confidence, "domain", "✍️")
        _render_confidence_badge(source_confidence, "domain")

        suggestions = domain_suggestion_chips(domain_value)
        if suggestions:
            st.caption(tr("Vorschläge", "Suggestions"))
            chip_cols = st.columns(len(suggestions))
            for idx, suggestion in enumerate(suggestions):

                def _apply_domain_suggestion(value: str = suggestion) -> None:
                    st.session_state[str(ProfilePaths.BUSINESS_CONTEXT_DOMAIN)] = value
                    business_context["domain"] = value
                    _update_profile(ProfilePaths.BUSINESS_CONTEXT_DOMAIN, value)
                    _ensure_badge(source_confidence, "domain", "🤖")

                chip_cols[idx].button(
                    suggestion,
                    key=f"business_context.domain.suggest.{idx}",
                    on_click=_apply_domain_suggestion,
                )

        render_section_heading(
            tr("Industrie-Codes (optional)", "Industry codes (optional)"),
            icon="🏷️",
            size="compact",
        )

        suggested_codes = suggest_esco_or_industry_codes(domain_value)
        existing_codes = business_context.get("industry_codes") or []
        code_options = list(dict.fromkeys([*suggested_codes, *existing_codes]))
        selected_codes = st.multiselect(
            tr("Branchenklassifikation", "Industry classification"),
            options=code_options,
            default=existing_codes,
            help=tr(
                "Automatisch vorgeschlagen aus der Business-Domain.",
                "Suggested automatically from the business domain.",
            ),
            key=str(ProfilePaths.BUSINESS_CONTEXT_INDUSTRY_CODES),
        )
        business_context["industry_codes"] = selected_codes
        _update_profile(ProfilePaths.BUSINESS_CONTEXT_INDUSTRY_CODES, selected_codes)
        if selected_codes and not source_confidence.get("industry_codes"):
            _ensure_badge(source_confidence, "industry_codes", "🤖")
        _render_confidence_badge(source_confidence, "industry_codes")
        if suggested_codes:
            st.caption(
                tr(
                    "Empfehlung: {codes}",
                    "Suggested: {codes}",
                ).format(codes=", ".join(suggested_codes))
            )

        with st.expander(tr("Organisation (optional)", "Organisation (optional)")):
            org_name_container = st.container()
            org_name = widget_factory.text_input(
                ProfilePaths.BUSINESS_CONTEXT_ORG_NAME,
                format_missing_label(
                    tr("Firma", "Company"),
                    field_path=ProfilePaths.COMPANY_NAME,
                    missing_fields=missing_here,
                ),
                widget_factory=org_name_container.text_input,
                placeholder=tr("z. B. Beispiel GmbH", "e.g. Example GmbH"),
                value_formatter=lambda value: str(value or ""),
            )
            business_context["org_name"] = org_name or None
            _update_profile(ProfilePaths.BUSINESS_CONTEXT_ORG_NAME, org_name or None)
            if org_name and not source_confidence.get("org_name"):
                _ensure_badge(source_confidence, "org_name", "✍️")
            _render_confidence_badge(source_confidence, "org_name")

            org_unit_container = st.container()
            org_unit = widget_factory.text_input(
                ProfilePaths.BUSINESS_CONTEXT_ORG_UNIT,
                format_missing_label(
                    tr("Abteilung/Team", "Department/team"),
                    field_path=ProfilePaths.DEPARTMENT_NAME,
                    missing_fields=missing_here,
                ),
                widget_factory=org_unit_container.text_input,
                placeholder=tr("z. B. Data Platform", "e.g. Data Platform"),
                value_formatter=lambda value: str(value or ""),
            )
            business_context["org_unit"] = org_unit or None
            _update_profile(ProfilePaths.BUSINESS_CONTEXT_ORG_UNIT, org_unit or None)
            if org_unit and not source_confidence.get("org_unit"):
                _ensure_badge(source_confidence, "org_unit", "✍️")
            _render_confidence_badge(source_confidence, "org_unit")

            location_container = st.container()
            location_value = widget_factory.text_input(
                ProfilePaths.BUSINESS_CONTEXT_LOCATION,
                format_missing_label(
                    tr("Standort", "Location"),
                    field_path=ProfilePaths.LOCATION_PRIMARY_CITY,
                    missing_fields=missing_here,
                ),
                widget_factory=location_container.text_input,
                placeholder=tr("z. B. Berlin / Hybrid", "e.g. Berlin / hybrid"),
                value_formatter=lambda value: str(value or ""),
            )
            business_context["location"] = location_value or None
            _update_profile(ProfilePaths.BUSINESS_CONTEXT_LOCATION, location_value or None)
            if location_value and not source_confidence.get("location"):
                _ensure_badge(source_confidence, "location", "✍️")
            _render_confidence_badge(source_confidence, "location")

        with st.expander(tr("Kontakt (optional)", "Contact (optional)")):
            contact_name_container = st.container()
            contact_name = widget_factory.text_input(
                ProfilePaths.COMPANY_CONTACT_NAME,
                tr("Kontaktperson", "Contact person"),
                widget_factory=contact_name_container.text_input,
                placeholder=tr("z. B. Max Mustermann", "e.g. Taylor Smith"),
                value_formatter=lambda value: str(value or ""),
            )
            _update_profile(ProfilePaths.COMPANY_CONTACT_NAME, contact_name or None)

            contact_email_container = st.container()
            contact_email_label = format_missing_label(
                tr("Kontakt-E-Mail", "Contact email"),
                field_path=ProfilePaths.COMPANY_CONTACT_EMAIL,
                missing_fields=missing_here,
            )
            contact_email = widget_factory.text_input(
                ProfilePaths.COMPANY_CONTACT_EMAIL,
                contact_email_label,
                widget_factory=contact_email_container.text_input,
                placeholder=tr("z. B. jobs@firma.de", "e.g. jobs@company.com"),
                value_formatter=lambda value: str(value or ""),
            )
            _update_profile(ProfilePaths.COMPANY_CONTACT_EMAIL, contact_email or None)

            contact_phone_container = st.container()
            contact_phone = widget_factory.text_input(
                ProfilePaths.COMPANY_CONTACT_PHONE,
                tr("Kontakt-Telefon", "Contact phone"),
                widget_factory=contact_phone_container.text_input,
                placeholder=tr("z. B. +49 30 1234567", "e.g. +49 30 1234567"),
                value_formatter=lambda value: str(value or ""),
            )
            _update_profile(ProfilePaths.COMPANY_CONTACT_PHONE, contact_phone or None)

        _sync_optional_org_fields(data, business_context)

    render_step_layout(
        title,
        None,
        known_cb=_render_business_context_known,
        missing_cb=_render_business_context_missing,
        missing_paths=missing_here,
        tools_cb=None,
    )


def _sync_optional_org_fields(profile: Mapping[str, Any], business_context: Mapping[str, Any]) -> None:
    company = profile.get("company") if isinstance(profile.get("company"), dict) else None
    department = profile.get("department") if isinstance(profile.get("department"), dict) else None
    location = profile.get("location") if isinstance(profile.get("location"), dict) else None

    org_name = str(business_context.get("org_name") or "").strip()
    if company is not None and org_name and not str(company.get("name") or "").strip():
        company["name"] = org_name
        _update_profile(ProfilePaths.COMPANY_NAME, org_name)

    org_unit = str(business_context.get("org_unit") or "").strip()
    if department is not None and org_unit and not str(department.get("name") or "").strip():
        department["name"] = org_unit
        _update_profile(ProfilePaths.DEPARTMENT_NAME, org_unit)

    org_location = str(business_context.get("location") or "").strip()
    if location is not None and org_location and not str(location.get("primary_city") or "").strip():
        location["primary_city"] = org_location
        _update_profile(ProfilePaths.LOCATION_PRIMARY_CITY, org_location)


def step_business_context(context: Any) -> None:
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_business_context()
