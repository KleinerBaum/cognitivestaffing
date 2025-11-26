from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache, partial
import logging
from types import ModuleType
from typing import Any, Iterable, Mapping, MutableMapping, cast
from urllib.parse import quote

import requests

import streamlit as st

import config
from components.chatkit_widget import render_chatkit_widget
from components import widget_factory
from constants.keys import ProfilePaths, StateKeys, UIKeys
from wizard.company_validators import persist_contact_email, persist_primary_city
from wizard.layout import (
    format_missing_label,
    merge_missing_help,
    render_missing_field_summary,
    render_step_heading,
    render_step_warning_banner,
)
from wizard_router import WizardContext
from utils.circuit_breaker import CircuitBreaker
from utils.i18n import tr

__all__ = ["step_company"]


logger = logging.getLogger(__name__)

_ASSISTANT_STATE_KEY = "company.insights.assistant"
_CIRCUIT_STORE: MutableMapping[str, Any] | None = None
_CLEARBIT_BREAKER_NAME = "clearbit.autocomplete"
_WIKIPEDIA_BREAKER_NAME = "wikipedia.summary"


def _get_circuit_store() -> MutableMapping[str, Any]:
    """Return the per-session circuit breaker store."""

    global _CIRCUIT_STORE
    if _CIRCUIT_STORE is None:
        try:
            _CIRCUIT_STORE = cast(MutableMapping[str, Any], st.session_state)
        except Exception:  # pragma: no cover - defensive fallback for tests
            _CIRCUIT_STORE = {}
    return _CIRCUIT_STORE


def _get_breaker(service_name: str) -> CircuitBreaker:
    """Instantiate a per-session circuit breaker for ``service_name``."""

    return CircuitBreaker(
        service_name,
        store=_get_circuit_store(),
        failure_threshold=3,
        recovery_timeout=60,
    )


def _render_service_warnings(skipped_services: Iterable[str], lang: str) -> None:
    """Surface user-facing notices for skipped external calls."""

    services = {service.lower() for service in skipped_services}
    if "clearbit" in services:
        st.info(
            tr(
                "Der Unternehmensdaten-Dienst ist vorübergehend nicht erreichbar – bitte manuell ergänzen.",
                "Company enrichment service is temporarily unavailable; you can proceed with manual input.",
                lang=lang,
            )
        )
    if "wikipedia" in services:
        st.info(
            tr(
                "Öffentliche Web-Hinweise wurden übersprungen, weil externe Quellen derzeit nicht erreichbar sind.",
                "Public web hints were skipped because external sources are currently unavailable.",
                lang=lang,
            )
        )


@dataclass
class CompanyLookupResult:
    name: str
    industry: str | None = None
    size: str | None = None
    hq_location: str | None = None
    website: str | None = None
    summary: str | None = None
    source: str | None = None
    disclaimer: str | None = None


def _load_sample_profiles() -> tuple[Mapping[str, str], ...]:
    """Return a small offline catalogue for demo lookups."""

    return (
        {
            "name": "OpenAI",
            "industry": "Artificial intelligence research and deployment",
            "size": "1500+",
            "hq_location": "San Francisco, United States",
            "website": "https://openai.com",
            "summary": "Research and deploy safe, beneficial AI across digital products and platforms.",
        },
        {
            "name": "Cofinpro AG",
            "industry": "Financial services consulting",
            "size": "200-500",
            "hq_location": "Frankfurt am Main, Germany",
            "website": "https://www.cofinpro.de",
            "summary": "German consultancy focused on banks and asset managers, covering technology delivery and strategy.",
        },
        {
            "name": "Notion Labs",
            "industry": "Productivity software",
            "size": "500-1000",
            "hq_location": "San Francisco, United States",
            "website": "https://www.notion.so",
            "summary": "Builds Notion, a connected workspace for docs, projects, and knowledge bases.",
        },
    )


def _get_assistant_state() -> dict[str, Any]:
    """Return persisted state for the insights assistant."""

    base_state = st.session_state.setdefault(
        _ASSISTANT_STATE_KEY,
        {"messages": [], "pending": [], "result": None},
    )
    if "messages" not in base_state or not isinstance(base_state.get("messages"), list):
        base_state["messages"] = []
    if "pending" not in base_state or not isinstance(base_state.get("pending"), list):
        base_state["pending"] = []
    return base_state


def _store_assistant_state(state: Mapping[str, Any]) -> None:
    """Persist the assistant state into session memory."""

    st.session_state[_ASSISTANT_STATE_KEY] = {
        "messages": list(state.get("messages", [])),
        "pending": list(state.get("pending", [])),
        "result": state.get("result"),
    }


@lru_cache(maxsize=32)
def _lookup_company_profile(company_name: str) -> tuple[CompanyLookupResult | None, set[str]]:
    """Try to find public company details via offline samples and light web lookups."""

    normalized = company_name.strip().lower()
    for sample in _load_sample_profiles():
        if sample.get("name", "").strip().lower() == normalized:
            return (
                CompanyLookupResult(
                    name=sample.get("name", company_name),
                    industry=sample.get("industry"),
                    size=sample.get("size"),
                    hq_location=sample.get("hq_location"),
                    website=sample.get("website"),
                    summary=sample.get("summary"),
                    source="offline_catalogue",
                    disclaimer="Static sample – please confirm accuracy.",
                ),
                set(),
            )

    web_result, skipped_services = _fetch_public_company_data(company_name)
    if web_result:
        return web_result, skipped_services
    return None, skipped_services


def _fetch_public_company_data(company_name: str) -> tuple[CompanyLookupResult | None, set[str]]:
    """Combine a lightweight web suggestion with a Wikipedia summary if available."""

    skipped_services: set[str] = set()
    wikipedia_summary, wikipedia_skipped = _fetch_wikipedia_summary(company_name)
    clearbit_profile, clearbit_skipped = _fetch_clearbit_profile(company_name)
    if wikipedia_skipped:
        skipped_services.add("wikipedia")
    if clearbit_skipped:
        skipped_services.add("clearbit")
    if not wikipedia_summary and not clearbit_profile:
        return None, skipped_services

    website = clearbit_profile.get("website") if clearbit_profile else None
    industry = clearbit_profile.get("industry") if clearbit_profile else None
    summary = None
    if wikipedia_summary:
        summary = wikipedia_summary.get("summary") or wikipedia_summary.get("description")
    elif clearbit_profile:
        summary = clearbit_profile.get("description")

    wikipedia_city = wikipedia_summary.get("title") if wikipedia_summary else None
    hq_location = clearbit_profile.get("hq_location") if clearbit_profile else None
    if not hq_location:
        hq_location = wikipedia_city

    resolved_name = str(clearbit_profile.get("name") if clearbit_profile else company_name).strip() or company_name

    return (
        CompanyLookupResult(
            name=resolved_name,
            industry=industry,
            size=clearbit_profile.get("size") if clearbit_profile else None,
            hq_location=hq_location,
            website=website,
            summary=summary,
            source="open_web",
            disclaimer=(
                "Public web hint – verify details before applying." if clearbit_profile or wikipedia_summary else None
            ),
        ),
        skipped_services,
    )


def _fetch_clearbit_profile(company_name: str) -> tuple[Mapping[str, str] | None, bool]:
    """Return a basic public profile suggestion from the Clearbit autocomplete API."""

    if not company_name.strip():
        return None, False
    breaker = _get_breaker(_CLEARBIT_BREAKER_NAME)
    if not breaker.allow_request():
        return None, True
    try:
        response = requests.get(
            "https://autocomplete.clearbit.com/v1/companies/suggest",
            params={"query": company_name},
            timeout=5,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:  # pragma: no cover - network dependency
        logger.debug("Unable to fetch company suggestion: %s", exc)
        breaker.record_failure()
        return None, False
    if not response.ok:
        breaker.record_failure()
        return None, False
    try:
        payload = response.json()
    except ValueError:
        breaker.record_failure()
        return None, False
    if not isinstance(payload, list):
        breaker.record_failure()
        return None, False
    first_hit = next((item for item in payload if isinstance(item, Mapping)), None)
    if not first_hit:
        breaker.record_success()
        return None, False
    name = str(first_hit.get("name") or company_name).strip()
    domain = str(first_hit.get("domain") or "").strip()
    website = f"https://{domain}" if domain else ""
    description = str(first_hit.get("description") or "").strip()
    breaker.record_success()
    return {"name": name, "website": website, "description": description}, False


def _fetch_wikipedia_summary(company_name: str) -> tuple[Mapping[str, str] | None, bool]:
    """Fetch a brief Wikipedia summary for the company if available."""

    if not company_name.strip():
        return None, False
    breaker = _get_breaker(_WIKIPEDIA_BREAKER_NAME)
    if not breaker.allow_request():
        return None, True
    try:
        response = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(company_name)}",
            timeout=5,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:  # pragma: no cover - network dependency
        logger.debug("Wikipedia summary lookup failed: %s", exc)
        breaker.record_failure()
        return None, False
    if not response.ok:
        breaker.record_failure()
        return None, False
    try:
        payload = response.json()
    except ValueError:
        breaker.record_failure()
        return None, False
    summary = str(payload.get("extract") or "").strip()
    description = str(payload.get("description") or "").strip()
    title = str(payload.get("title") or company_name).strip()
    if not summary and not description:
        breaker.record_success()
        return None, False
    breaker.record_success()
    return {
        "summary": summary or description,
        "description": description,
        "title": title,
    }, False


def _describe_lookup_result(result: CompanyLookupResult, lang: str) -> str:
    """Return a localized markdown block describing the lookup result."""

    lines: list[str] = []
    lines.append(tr("Gefundene Hinweise:", "Found signals:", lang=lang))
    if result.industry:
        lines.append(f"- {tr('Branche', 'Industry', lang=lang)}: {result.industry}")
    if result.size:
        lines.append(f"- {tr('Größe', 'Size', lang=lang)}: {result.size}")
    if result.hq_location:
        lines.append(f"- {tr('Hauptsitz', 'Headquarters', lang=lang)}: {result.hq_location}")
    if result.website:
        lines.append(f"- {tr('Website', 'Website', lang=lang)}: {result.website}")
    if result.summary:
        lines.append(f"- {tr('Kurzbeschreibung', 'Short summary', lang=lang)}: {result.summary}")
    if not any([result.industry, result.size, result.hq_location, result.website, result.summary]):
        lines.append(tr("Keine verwertbaren Details gefunden.", "No usable details found.", lang=lang))
    if result.disclaimer:
        lines.append(f"_{result.disclaimer}_")
    if result.source:
        lines.append(tr("Quelle: {source}", "Source: {source}", lang=lang).format(source=result.source))
    return "\n".join(lines)


def _apply_company_insights(
    company: dict[str, Any],
    result: CompanyLookupResult,
    lang: str,
) -> list[str]:
    """Apply lookup data to the profile where fields are still empty."""

    applied: list[str] = []
    if result.industry and not (company.get("industry") or "").strip():
        company["industry"] = result.industry
        _update_profile(ProfilePaths.COMPANY_INDUSTRY, result.industry)
        applied.append(tr("Branche aktualisiert", "Updated industry", lang=lang))
    if result.size and not (company.get("size") or "").strip():
        company["size"] = result.size
        _update_profile(ProfilePaths.COMPANY_SIZE, result.size)
        applied.append(tr("Größe ergänzt", "Added size", lang=lang))
    if result.hq_location and not (company.get("hq_location") or "").strip():
        company["hq_location"] = result.hq_location
        _update_profile(ProfilePaths.COMPANY_HQ_LOCATION, result.hq_location)
        applied.append(tr("Hauptsitz gesetzt", "Set headquarters", lang=lang))
    if result.website and not (company.get("website") or "").strip():
        company["website"] = result.website
        _update_profile(ProfilePaths.COMPANY_WEBSITE, result.website)
        applied.append(tr("Website ergänzt", "Added website", lang=lang))
    if result.summary and not (company.get("description") or "").strip():
        company["description"] = result.summary
        _update_profile(ProfilePaths.COMPANY_DESCRIPTION, result.summary)
        applied.append(tr("Kurzbeschreibung eingefügt", "Inserted short description", lang=lang))
    if applied:
        st.toast(tr("Vorschläge übernommen.", "Suggestions applied.", lang=lang), icon="✅")
    else:
        st.info(
            tr(
                "Keine Felder überschrieben – vorhandene Angaben bleiben bestehen.",
                "Nothing changed – existing values are kept.",
                lang=lang,
            )
        )
    return applied


def _build_company_questions(lang: str) -> list[dict[str, str]]:
    """Return the ordered list of questions for missing details."""

    return [
        {
            "field": "industry",
            "label": tr("Branche", "Industry", lang=lang),
            "question": tr(
                "Welche Branche beschreibt das Unternehmen am besten?",
                "Which industry best describes the company?",
                lang=lang,
            ),
        },
        {
            "field": "size",
            "label": tr("Unternehmensgröße", "Company size", lang=lang),
            "question": tr(
                "Wie viele Mitarbeitende (oder Größenkategorie) hat das Unternehmen?",
                "Roughly how many employees does the company have?",
                lang=lang,
            ),
        },
        {
            "field": "hq_location",
            "label": tr("Hauptsitz", "Headquarters", lang=lang),
            "question": tr(
                "Wo befindet sich der Hauptsitz?",
                "Where is the headquarters located?",
                lang=lang,
            ),
        },
        {
            "field": "website",
            "label": tr("Website", "Website", lang=lang),
            "question": tr(
                "Wie lautet die Unternehmenswebsite?",
                "What is the official company website?",
                lang=lang,
            ),
        },
        {
            "field": "description",
            "label": tr("Kurzbeschreibung", "Short description", lang=lang),
            "question": tr(
                "Bitte formuliere eine kurze Unternehmensbeschreibung (1-2 Sätze).",
                "Please share a short company blurb (1-2 sentences).",
                lang=lang,
            ),
        },
    ]


def _render_company_insights_assistant(company: dict[str, Any], location_data: dict[str, Any]) -> None:
    """Render the ChatKit-style assistant for company enrichment."""

    lang = st.session_state.get("lang", "de")
    state = _get_assistant_state()
    questions = _build_company_questions(lang)
    with st.expander(
        tr("🧠 KI-Unterstützung für Unternehmensprofil", "🧠 Company insights assistant", lang=lang),
        expanded=False,
    ):
        st.caption(
            tr(
                "Fragt öffentliche Quellen ab oder sammelt fehlende Details zum Unternehmen.",
                "Checks public sources or collects missing company details.",
                lang=lang,
            )
        )

        company_name = (company.get("name") or "").strip()
        if not company_name:
            st.info(
                tr(
                    "Bitte zuerst den offiziellen Firmennamen angeben.",
                    "Please provide the official company name first.",
                    lang=lang,
                )
            )
            _store_assistant_state(state)
            return

        city_hint = (location_data.get("primary_city") or "").strip()
        if city_hint and not (company.get("hq_location") or "").strip():
            st.caption(
                tr(
                    "Tipp: Wir nutzen {city} als Ausgangspunkt für den Hauptsitz – passe ihn bei Bedarf an.",
                    "Hint: Using {city} as a starting point for the headquarters – adjust as needed.",
                    lang=lang,
                ).format(city=city_hint)
            )

        chatkit_workflow = config.CHATKIT_COMPANY_WORKFLOW_ID
        if chatkit_workflow:
            with st.expander(
                tr("💬 ChatKit-Unternehmenschat", "💬 ChatKit company chat", lang=lang),
                expanded=False,
            ):
                render_chatkit_widget(
                    workflow_id=chatkit_workflow,
                    conversation_key="company.assistant",
                    title_md=tr(
                        "##### Live-Chat für Firmenprofil",
                        "##### Live chat for the company profile",
                        lang=lang,
                    ),
                    description=tr(
                        "Hole fehlende Branchendetails oder HQ/Website-Angaben per ChatKit ein.",
                        "Use ChatKit to gather missing industry, HQ, or website details.",
                        lang=lang,
                    ),
                    lang=lang,
                    height=520,
                )
            st.write("---")

        lookup_col, apply_col = st.columns((1.4, 1))
        if lookup_col.button(
            tr("🔎 Öffentliche Firmendaten abrufen", "🔎 Fetch public company data", lang=lang),
            key="company.insights.lookup",
        ):
            fresh_result, skipped_services = _lookup_company_profile(company_name)
            state["result"] = fresh_result
            state["skipped_services"] = list(skipped_services)
            if fresh_result:
                st.success(tr("Hinweise gefunden.", "Found public hints.", lang=lang))
            else:
                st.warning(
                    tr(
                        "Keine Treffer – bitte manuell ergänzen.",
                        "No matches – please add details manually.",
                        lang=lang,
                    )
                )

        lookup_result = cast(CompanyLookupResult | None, state.get("result"))
        skipped_services = set(cast(list[str] | set[str] | None, state.get("skipped_services")) or [])
        if skipped_services:
            _render_service_warnings(skipped_services, lang)
        if lookup_result:
            st.markdown(_describe_lookup_result(lookup_result, lang))
            if lookup_result.disclaimer:
                st.caption(tr("Hinweis: {text}", "Disclaimer: {text}", lang=lang).format(text=lookup_result.disclaimer))
            if apply_col.button(
                tr("Vorschläge übernehmen", "Apply suggestions", lang=lang),
                key="company.insights.apply",
            ):
                _apply_company_insights(company, lookup_result, lang)

        missing_fields: list[str] = []
        for descriptor in questions:
            field = descriptor.get("field")
            if not field:
                continue
            if field == "hq_location" and not (company.get("hq_location") or "").strip():
                missing_fields.append(field)
            elif field == "industry" and not (company.get("industry") or "").strip():
                missing_fields.append(field)
            elif field == "size" and not (company.get("size") or "").strip():
                missing_fields.append(field)
            elif field == "website" and not (company.get("website") or "").strip():
                missing_fields.append(field)
            elif field == "description" and not (company.get("description") or "").strip():
                missing_fields.append(field)

        pending = [field for field in state.get("pending", []) if field in missing_fields]
        for field in missing_fields:
            if field not in pending:
                pending.append(field)
        state["pending"] = pending

        if not state.get("messages") and pending:
            friendly_labels = [descriptor["label"] for descriptor in questions if descriptor.get("field") in pending]
            intro = tr(
                "Ich kann folgende Punkte ergänzen: {labels}.",
                "I can help capture these: {labels}.",
                lang=lang,
            ).format(labels=", ".join(friendly_labels))
            state["messages"] = [
                {"role": "assistant", "content": intro, "field": None},
            ]

        current_field = pending[0] if pending else None
        if current_field and not any(
            message.get("role") == "assistant" and message.get("field") == current_field
            for message in state.get("messages", [])
        ):
            descriptor_lookup: dict[str, dict[str, str]] = {
                str(item["field"]): item for item in questions if item.get("field")
            }
            question_text = descriptor_lookup.get(current_field, {}).get("question")
            if question_text:
                state.setdefault("messages", []).append(
                    {"role": "assistant", "content": question_text, "field": current_field}
                )

        for message in state.get("messages", []):
            role = str(message.get("role") or "assistant")
            content = str(message.get("content") or "")
            if not content.strip():
                continue
            st.chat_message(role).markdown(content)

        prompt = st.chat_input(
            tr("Antwort eingeben …", "Share your answer …", lang=lang),
            key="company.insights.input",
            disabled=not current_field,
        )
        if prompt is not None:
            normalized = prompt.strip()
            if not normalized:
                st.toast(
                    tr("Bitte eine kurze Antwort eingeben.", "Please enter a short answer.", lang=lang),
                    icon="ℹ️",
                )
            else:
                if current_field is None:
                    _store_assistant_state(state)
                    return
                state.setdefault("messages", []).append({"role": "user", "content": normalized, "field": current_field})
                if current_field == "industry":
                    company["industry"] = normalized
                    _update_profile(ProfilePaths.COMPANY_INDUSTRY, normalized)
                elif current_field == "size":
                    company["size"] = normalized
                    _update_profile(ProfilePaths.COMPANY_SIZE, normalized)
                elif current_field == "hq_location":
                    company["hq_location"] = normalized
                    _update_profile(ProfilePaths.COMPANY_HQ_LOCATION, normalized)
                elif current_field == "website":
                    company["website"] = normalized
                    _update_profile(ProfilePaths.COMPANY_WEBSITE, normalized)
                elif current_field == "description":
                    company["description"] = normalized
                    _update_profile(ProfilePaths.COMPANY_DESCRIPTION, normalized)

                label_lookup: dict[str, str] = {
                    str(item["field"]): str(item.get("label") or "") for item in questions if item.get("field")
                }
                ack = tr("Gespeichert: {label}.", "Saved: {label}.", lang=lang).format(
                    label=label_lookup.get(current_field, current_field)
                )
                state["messages"].append({"role": "assistant", "content": ack, "field": current_field})
                pending = [field for field in pending if field != current_field]
                state["pending"] = pending
                if pending:
                    next_field: str = pending[0]
                    descriptor_lookup = {str(item["field"]): item for item in questions if item.get("field")}
                    follow_up = descriptor_lookup.get(next_field, {}).get("question")
                    if follow_up:
                        state["messages"].append({"role": "assistant", "content": follow_up, "field": next_field})
                else:
                    state["messages"].append(
                        {
                            "role": "assistant",
                            "content": tr(
                                "Danke – alle angefragten Felder sind nun ausgefüllt.",
                                "Thanks – all requested fields are now filled.",
                                lang=lang,
                            ),
                            "field": None,
                        }
                    )
        _store_assistant_state(state)


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "COMPACT_STEP_STYLE",
    "COMPANY_CONTACT_EMAIL_CAPTION",
    "COMPANY_CONTACT_EMAIL_LABEL",
    "COMPANY_CONTACT_EMAIL_PLACEHOLDER",
    "COMPANY_CONTACT_NAME_LABEL",
    "COMPANY_CONTACT_NAME_PLACEHOLDER",
    "COMPANY_CONTACT_PHONE_LABEL",
    "COMPANY_CONTACT_PHONE_PLACEHOLDER",
    "COMPANY_NAME_HELP",
    "COMPANY_NAME_LABEL",
    "COMPANY_NAME_PLACEHOLDER",
    "CONTACT_EMAIL_PATTERN_WARNING",
    "PRIMARY_CITY_CAPTION",
    "PRIMARY_CITY_LABEL",
    "PRIMARY_CITY_PLACEHOLDER",
    "PRIMARY_COUNTRY_LABEL",
    "PRIMARY_COUNTRY_PLACEHOLDER",
    "REQUIRED_SUFFIX",
    "_apply_field_lock_kwargs",
    "_autofill_was_rejected",
    "_build_profile_context",
    "_collect_combined_certificates",
    "_email_format_invalid",
    "_field_lock_config",
    "_format_dynamic_message",
    "_get_company_logo_bytes",
    "_get_profile_state",
    "_missing_fields_for_section",
    "_persist_branding_asset_from_state",
    "_render_autofill_suggestion",
    "_render_company_research_tools",
    "_render_followups_for_fields",
    "_render_followups_for_step",
    "_render_prefill_badge",
    "_set_company_logo",
    "_set_requirement_certificates",
    "_string_or_empty",
    "_update_profile",
)

COMPACT_STEP_STYLE: Any = cast(Any, None)
COMPANY_CONTACT_EMAIL_CAPTION: Any = cast(Any, None)
COMPANY_CONTACT_EMAIL_LABEL: Any = cast(Any, None)
COMPANY_CONTACT_EMAIL_PLACEHOLDER: Any = cast(Any, None)
COMPANY_CONTACT_NAME_LABEL: Any = cast(Any, None)
COMPANY_CONTACT_NAME_PLACEHOLDER: Any = cast(Any, None)
COMPANY_CONTACT_PHONE_LABEL: Any = cast(Any, None)
COMPANY_CONTACT_PHONE_PLACEHOLDER: Any = cast(Any, None)
COMPANY_NAME_HELP: Any = cast(Any, None)
COMPANY_NAME_LABEL: Any = cast(Any, None)
COMPANY_NAME_PLACEHOLDER: Any = cast(Any, None)
CONTACT_EMAIL_PATTERN_WARNING: Any = cast(Any, None)
PRIMARY_CITY_CAPTION: Any = cast(Any, None)
PRIMARY_CITY_LABEL: Any = cast(Any, None)
PRIMARY_CITY_PLACEHOLDER: Any = cast(Any, None)
PRIMARY_COUNTRY_LABEL: Any = cast(Any, None)
PRIMARY_COUNTRY_PLACEHOLDER: Any = cast(Any, None)
REQUIRED_SUFFIX: Any = cast(Any, None)
_apply_field_lock_kwargs: Any = cast(Any, None)
_autofill_was_rejected: Any = cast(Any, None)
_build_profile_context: Any = cast(Any, None)
_collect_combined_certificates: Any = cast(Any, None)
_email_format_invalid: Any = cast(Any, None)
_field_lock_config: Any = cast(Any, None)
_format_dynamic_message: Any = cast(Any, None)
_get_company_logo_bytes: Any = cast(Any, None)
_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_persist_branding_asset_from_state: Any = cast(Any, None)
_render_autofill_suggestion: Any = cast(Any, None)
_render_company_research_tools: Any = cast(Any, None)
_render_followups_for_fields: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_prefill_badge: Any = cast(Any, None)
_set_company_logo: Any = cast(Any, None)
_set_requirement_certificates: Any = cast(Any, None)
_string_or_empty: Any = cast(Any, None)
_update_profile: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    bound: list[str] = []
    missing: list[str] = []

    for name in _FLOW_DEPENDENCIES:
        if hasattr(flow, name):
            globals()[name] = getattr(flow, name)
            bound.append(name)
        else:
            missing.append(name)

    if bound:
        logger.debug("Bound company step dependencies: %s", ", ".join(sorted(bound)))
    if missing:
        logger.warning("Missing flow dependencies for company step: %s", ", ".join(sorted(missing)))


def _step_company() -> None:
    """Render the company information step.

    Returns:
        None
    """

    st.markdown(COMPACT_STEP_STYLE, unsafe_allow_html=True)

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)
    company_header = _format_dynamic_message(
        default=("Unternehmen", "Company"),
        context=profile_context,
        variants=[
            (
                (
                    "{company_name} in {primary_city}",
                    "{company_name} in {primary_city}",
                ),
                ("company_name", "primary_city"),
            ),
            (
                (
                    "{company_name} im Überblick",
                    "{company_name} overview",
                ),
                ("company_name",),
            ),
        ],
    )
    missing_here = _missing_fields_for_section(1)

    company_caption = _format_dynamic_message(
        default=(
            "Basisinformationen zum Unternehmen angeben.",
            "Provide basic information about the company.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Basisinformationen zu {company_name} in {primary_city} ergänzen.",
                    "Add the essentials for {company_name} in {primary_city}.",
                ),
                ("company_name", "primary_city"),
            ),
            (
                (
                    "Basisinformationen zu {company_name} ergänzen.",
                    "Add the essentials for {company_name}.",
                ),
                ("company_name",),
            ),
        ],
    )
    render_step_heading(company_header, company_caption, missing_fields=missing_here)
    render_step_warning_banner()
    render_missing_field_summary(missing_here)
    data = profile
    company = data.setdefault("company", {})
    position = data.setdefault("position", {})
    department = data.setdefault("department", {})
    team = data.setdefault("team", {})
    location_data = data.setdefault("location", {})
    combined_certificates = _collect_combined_certificates(data["requirements"])
    _set_requirement_certificates(data["requirements"], combined_certificates)
    label_company = format_missing_label(
        tr(*COMPANY_NAME_LABEL) + REQUIRED_SUFFIX,
        field_path=ProfilePaths.COMPANY_NAME,
        missing_fields=missing_here,
    )
    company_lock = _field_lock_config(
        ProfilePaths.COMPANY_NAME,
        label_company,
        container=st,
        context="step",
    )
    company_kwargs = _apply_field_lock_kwargs(
        company_lock,
        {
            "help": merge_missing_help(
                tr(*COMPANY_NAME_HELP),
                field_path=ProfilePaths.COMPANY_NAME,
                missing_fields=missing_here,
            )
        },
    )

    company_identity_container = st.container()

    _render_company_insights_assistant(company, location_data)
    _render_company_research_tools(company.get("website", ""))

    with company_identity_container:
        company["name"] = widget_factory.text_input(
            ProfilePaths.COMPANY_NAME,
            company_lock["label"],
            placeholder=tr(*COMPANY_NAME_PLACEHOLDER),
            value_formatter=_string_or_empty,
            **company_kwargs,
        )
        _render_prefill_badge(company_lock, container=company_identity_container)
        if ProfilePaths.COMPANY_NAME in missing_here and not company["name"]:
            st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))
        _render_followups_for_fields(
            (ProfilePaths.COMPANY_NAME,),
            data,
            container_factory=st.container,
        )

        hq_col, size_col, industry_col = st.columns(3, gap="small")
        hq_initial = _string_or_empty(company.get("hq_location"))
        if not hq_initial.strip():
            city_hint = _string_or_empty(location_data.get("primary_city"))
            if city_hint.strip():
                hq_initial = city_hint.strip()
        company["hq_location"] = widget_factory.text_input(
            ProfilePaths.COMPANY_HQ_LOCATION,
            tr("Hauptsitz", "Headquarters"),
            widget_factory=hq_col.text_input,
            placeholder=tr("Stadt und Land eingeben", "Enter city and country"),
            default=hq_initial,
            value_formatter=_string_or_empty,
        )
        company["size"] = widget_factory.text_input(
            ProfilePaths.COMPANY_SIZE,
            tr("Größe", "Size"),
            widget_factory=size_col.text_input,
            placeholder=tr("Unternehmensgröße eintragen", "Enter the company size"),
            value_formatter=_string_or_empty,
        )
        company["industry"] = widget_factory.text_input(
            ProfilePaths.COMPANY_INDUSTRY,
            tr("Branche", "Industry"),
            widget_factory=industry_col.text_input,
            placeholder=tr("Branche beschreiben", "Describe the industry"),
            value_formatter=_string_or_empty,
        )

    website_col, mission_col = st.columns(2, gap="small")
    company["website"] = widget_factory.text_input(
        ProfilePaths.COMPANY_WEBSITE,
        tr("Website", "Website"),
        widget_factory=website_col.text_input,
        placeholder=tr("Unternehmenswebsite eingeben", "Enter the company website"),
        value_formatter=_string_or_empty,
    )
    company["mission"] = widget_factory.text_input(
        ProfilePaths.COMPANY_MISSION,
        tr("Mission", "Mission"),
        widget_factory=mission_col.text_input,
        placeholder=tr(
            "Mission in eigenen Worten beschreiben",
            "Describe the company mission",
        ),
        value_formatter=_string_or_empty,
    )

    description = st.text_area(
        tr("Unternehmensbeschreibung", "Company description"),
        value=_string_or_empty(company.get("description")),
        placeholder=tr(
            "Kurzbeschreibung des Unternehmens (max. 50 Wörter)",
            "Brief company overview (max. 50 words)",
        ),
        key="ui.company.description",
    )
    _update_profile(ProfilePaths.COMPANY_DESCRIPTION, description)
    company["description"] = description

    company["culture"] = widget_factory.text_input(
        ProfilePaths.COMPANY_CULTURE,
        tr("Unternehmenskultur", "Company culture"),
        placeholder=tr(
            "Unternehmenskultur skizzieren",
            "Summarise the company culture",
        ),
        value_formatter=_string_or_empty,
    )

    contact_cols = st.columns((1.2, 1.2, 1), gap="small")
    widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_NAME,
        format_missing_label(
            tr(*COMPANY_CONTACT_NAME_LABEL),
            field_path=ProfilePaths.COMPANY_CONTACT_NAME,
            missing_fields=missing_here,
        ),
        widget_factory=contact_cols[0].text_input,
        placeholder=tr(*COMPANY_CONTACT_NAME_PLACEHOLDER),
        value_formatter=_string_or_empty,
        help=merge_missing_help(
            None,
            field_path=ProfilePaths.COMPANY_CONTACT_NAME,
            missing_fields=missing_here,
        ),
    )
    _render_followups_for_fields(
        (ProfilePaths.COMPANY_CONTACT_NAME,),
        data,
        container_factory=contact_cols[0].container,
    )
    contact_email_label = format_missing_label(
        tr(*COMPANY_CONTACT_EMAIL_LABEL) + REQUIRED_SUFFIX,
        field_path=ProfilePaths.COMPANY_CONTACT_EMAIL,
        missing_fields=missing_here,
    )
    contact_email_value = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        contact_email_label,
        widget_factory=contact_cols[1].text_input,
        placeholder=tr(*COMPANY_CONTACT_EMAIL_PLACEHOLDER),
        value_formatter=_string_or_empty,
        allow_callbacks=False,
        sync_session_state=False,
        help=merge_missing_help(
            tr(*COMPANY_CONTACT_EMAIL_CAPTION),
            field_path=ProfilePaths.COMPANY_CONTACT_EMAIL,
            missing_fields=missing_here,
        ),
    )
    contact_cols[1].caption(tr(*COMPANY_CONTACT_EMAIL_CAPTION))
    if _email_format_invalid(contact_email_value):
        contact_cols[1].warning(tr(*CONTACT_EMAIL_PATTERN_WARNING))
    _, contact_email_error = persist_contact_email(contact_email_value)
    if contact_email_error:
        contact_cols[1].error(tr(*contact_email_error))
    _render_followups_for_fields(
        (ProfilePaths.COMPANY_CONTACT_EMAIL,),
        data,
        container_factory=contact_cols[1].container,
    )
    phone_label = format_missing_label(
        tr(*COMPANY_CONTACT_PHONE_LABEL) + REQUIRED_SUFFIX,
        field_path=ProfilePaths.COMPANY_CONTACT_PHONE,
        missing_fields=missing_here,
    )
    contact_phone = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_PHONE,
        phone_label,
        widget_factory=contact_cols[2].text_input,
        placeholder=tr(*COMPANY_CONTACT_PHONE_PLACEHOLDER),
        value_formatter=_string_or_empty,
        help=merge_missing_help(
            None,
            field_path=ProfilePaths.COMPANY_CONTACT_PHONE,
            missing_fields=missing_here,
        ),
    )
    if ProfilePaths.COMPANY_CONTACT_PHONE in missing_here and not (contact_phone or "").strip():
        contact_cols[2].caption(tr("Dieses Feld ist erforderlich", "This field is required"))
    _render_followups_for_fields(
        (ProfilePaths.COMPANY_CONTACT_PHONE,),
        data,
        container_factory=contact_cols[2].container,
    )

    city_col, country_col = st.columns(2, gap="small")
    city_label = format_missing_label(
        tr(*PRIMARY_CITY_LABEL) + REQUIRED_SUFFIX,
        field_path=ProfilePaths.LOCATION_PRIMARY_CITY,
        missing_fields=missing_here,
    )
    city_lock = _field_lock_config(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        city_label,
        container=city_col,
        context="step",
    )
    city_kwargs = _apply_field_lock_kwargs(
        city_lock,
        {
            "help": merge_missing_help(
                tr(*PRIMARY_CITY_CAPTION),
                field_path=ProfilePaths.LOCATION_PRIMARY_CITY,
                missing_fields=missing_here,
            )
        },
    )
    city_value_input = widget_factory.text_input(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        city_lock["label"],
        widget_factory=city_col.text_input,
        placeholder=tr(*PRIMARY_CITY_PLACEHOLDER),
        value_formatter=_string_or_empty,
        allow_callbacks=False,
        sync_session_state=False,
        **city_kwargs,
    )
    _render_prefill_badge(city_lock, container=city_col)
    city_col.caption(tr(*PRIMARY_CITY_CAPTION))
    _, primary_city_error = persist_primary_city(city_value_input)
    if primary_city_error:
        city_col.error(tr(*primary_city_error))
    _render_followups_for_fields(
        (ProfilePaths.LOCATION_PRIMARY_CITY,),
        data,
        container_factory=city_col.container,
    )

    country_label = format_missing_label(
        tr(*PRIMARY_COUNTRY_LABEL) + REQUIRED_SUFFIX,
        field_path=ProfilePaths.LOCATION_COUNTRY,
        missing_fields=missing_here,
    )
    country_lock = _field_lock_config(
        ProfilePaths.LOCATION_COUNTRY,
        country_label,
        container=country_col,
        context="step",
    )
    country_kwargs = _apply_field_lock_kwargs(
        country_lock,
        {
            "help": merge_missing_help(
                None,
                field_path=ProfilePaths.LOCATION_COUNTRY,
                missing_fields=missing_here,
            )
        },
    )
    location_data["country"] = widget_factory.text_input(
        ProfilePaths.LOCATION_COUNTRY,
        country_lock["label"],
        widget_factory=country_col.text_input,
        placeholder=tr(*PRIMARY_COUNTRY_PLACEHOLDER),
        value_formatter=_string_or_empty,
        **country_kwargs,
    )
    _render_prefill_badge(country_lock, container=country_col)
    if ProfilePaths.LOCATION_COUNTRY in missing_here and not location_data.get("country"):
        country_col.caption(tr("Dieses Feld ist erforderlich", "This field is required"))
    _render_followups_for_fields(
        (ProfilePaths.LOCATION_COUNTRY,),
        data,
        container_factory=country_col.container,
    )

    city_value = (location_data.get("primary_city") or "").strip()
    country_value = (location_data.get("country") or "").strip()
    hq_value = (company.get("hq_location") or "").strip()
    suggested_hq_parts = [part for part in (city_value, country_value) if part]
    suggested_hq = ", ".join(suggested_hq_parts)
    if suggested_hq and not hq_value and not _autofill_was_rejected(ProfilePaths.COMPANY_HQ_LOCATION, suggested_hq):
        if city_value and country_value:
            description = tr(
                "Stadt und Land kombiniert – soll das der Hauptsitz sein?",
                "Combined city and country into a potential headquarters.",
            )
        elif city_value:
            description = tr(
                "Nur Stadt vorhanden – als Hauptsitz übernehmen?",
                "Only city provided – use it as headquarters?",
            )
        else:
            description = tr(
                "Nur Land vorhanden – als Hauptsitz übernehmen?",
                "Only country provided – use it as headquarters?",
            )
        _render_autofill_suggestion(
            field_path=ProfilePaths.COMPANY_HQ_LOCATION,
            suggestion=suggested_hq,
            title=tr("🏙️ Hauptsitz übernehmen?", "🏙️ Use this as headquarters?"),
            description=description,
            icon="🏙️",
            success_message=tr(
                "Hauptsitz mit Standortangaben gefüllt.",
                "Headquarters filled from location details.",
            ),
            rejection_message=tr(
                "Vorschlag ignoriert – wir fragen nicht erneut.",
                "Suggestion dismissed – we will not offer it again.",
            ),
        )

    dept_cols = st.columns(2, gap="small")
    department["name"] = dept_cols[0].text_input(
        tr("Abteilung", "Department"),
        value=department.get("name", ""),
        key=ProfilePaths.DEPARTMENT_NAME,
        placeholder=tr("Abteilung beschreiben", "Describe the department"),
    )
    _update_profile(ProfilePaths.DEPARTMENT_NAME, department.get("name", ""))
    _render_followups_for_fields(
        (ProfilePaths.DEPARTMENT_NAME,),
        data,
        container_factory=dept_cols[0].container,
    )
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

    reporting_cols = st.columns((1, 1), gap="small")
    team_reporting_value = reporting_cols[0].text_input(
        tr("Berichtslinie", "Reporting line"),
        value=team.get("reporting_line", position.get("reporting_line", "")),
        key=ProfilePaths.TEAM_REPORTING_LINE,
        placeholder=tr("Berichtslinie erläutern", "Describe the reporting line"),
    )
    team["reporting_line"] = team_reporting_value
    _update_profile(ProfilePaths.TEAM_REPORTING_LINE, team_reporting_value)
    position["reporting_line"] = team_reporting_value
    _update_profile(ProfilePaths.POSITION_REPORTING_LINE, team_reporting_value)
    _render_followups_for_fields(
        (ProfilePaths.TEAM_REPORTING_LINE,),
        data,
        container_factory=reporting_cols[0].container,
    )

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

    brand_cols = st.columns((2, 1), gap="small")
    company["brand_name"] = brand_cols[0].text_input(
        tr("Marke/Tochterunternehmen", "Brand/Subsidiary"),
        value=_string_or_empty(company.get("brand_name")),
        placeholder=tr(
            "Marken- oder Tochtername eintragen",
            "Enter the brand or subsidiary name",
        ),
    )
    company["claim"] = brand_cols[0].text_input(
        tr("Claim/Slogan", "Claim/Tagline"),
        value=_string_or_empty(company.get("claim")),
        placeholder=tr("Claim hinzufügen", "Add claim"),
    )
    company["brand_color"] = brand_cols[0].text_input(
        tr("Markenfarbe (Hex)", "Brand color (hex)"),
        value=_string_or_empty(company.get("brand_color")),
        placeholder=tr("Hex-Farbcode eingeben", "Enter a hex colour code"),
    )

    with brand_cols[1]:
        company["logo_url"] = st.text_input(
            tr("Logo-URL", "Logo URL"),
            value=_string_or_empty(company.get("logo_url")),
            placeholder=tr("Logo-URL hinzufügen", "Add logo URL"),
        )
        st.file_uploader(
            tr("Branding-Assets", "Brand assets"),
            type=["png", "jpg", "jpeg", "svg", "pdf"],
            key=UIKeys.COMPANY_BRANDING_UPLOAD_LEGACY,
            on_change=partial(
                _persist_branding_asset_from_state,
                UIKeys.COMPANY_BRANDING_UPLOAD_LEGACY,
            ),
        )

        branding_asset = st.session_state.get(StateKeys.COMPANY_BRANDING_ASSET)
        if branding_asset:
            asset_name = branding_asset.get("name") or tr("Hochgeladene Datei", "Uploaded file")
            st.caption(
                tr(
                    "Aktuelle Datei: {name}",
                    "Current asset: {name}",
                ).format(name=asset_name)
            )
            if isinstance(branding_asset.get("data"), (bytes, bytearray)) and str(
                branding_asset.get("type", "")
            ).startswith("image/"):
                try:
                    st.image(branding_asset["data"], width=160)
                except Exception:  # pragma: no cover - graceful fallback
                    pass
            if st.button(
                tr("Datei entfernen", "Remove file"),
                key="company.branding.remove",
            ):
                st.session_state.pop(StateKeys.COMPANY_BRANDING_ASSET, None)
                for upload_key in (
                    UIKeys.COMPANY_BRANDING_UPLOAD,
                    UIKeys.COMPANY_BRANDING_UPLOAD_LEGACY,
                ):
                    st.session_state.pop(upload_key, None)
                st.rerun()

        logo_upload = st.file_uploader(
            tr("Logo hochladen (optional)", "Upload logo (optional)"),
            type=["png", "jpg", "jpeg", "svg"],
            key=UIKeys.COMPANY_LOGO,
        )
        if logo_upload is not None:
            _set_company_logo(logo_upload.getvalue())

        logo_bytes = _get_company_logo_bytes()
        if logo_bytes:
            try:
                st.image(logo_bytes, caption=tr("Aktuelles Logo", "Current logo"), width=160)
            except Exception:
                st.caption(tr("Logo erfolgreich geladen.", "Logo uploaded successfully."))
            if st.button(tr("Logo entfernen", "Remove logo"), key="company.logo.remove"):
                _set_company_logo(None)
                st.rerun()

    # Inline follow-up questions for Company section
    _render_followups_for_step("company", data)


def step_company(context: WizardContext) -> None:
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_company()
