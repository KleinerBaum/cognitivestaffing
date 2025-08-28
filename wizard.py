# wizard.py — Vacalyser Wizard (clean flow, schema-aligned)
from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from typing import List

import re
import streamlit as st

from utils.i18n import tr
from i18n import t
from constants.keys import UIKeys, StateKeys
from utils.session import bind_textarea
from state.ensure_state import ensure_state
from ingest.extractors import extract_text_from_file, extract_text_from_url
from utils.errors import display_error
from models.need_analysis import NeedAnalysisProfile

# LLM/ESCO und Follow-ups
from openai_utils import (
    extract_with_function,  # nutzt deine neue Definition
    generate_interview_guide,
    generate_job_ad,
    suggest_skills_for_role,
)
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from integrations.esco import search_occupation, enrich_skills
from components.stepper import render_stepper
from utils import build_boolean_search
from nlp.bias import scan_bias_language

ROOT = Path(__file__).parent
ensure_state()


def next_step() -> None:
    """Advance the wizard to the next step."""

    st.session_state[StateKeys.STEP] = st.session_state.get(StateKeys.STEP, 0) + 1


def prev_step() -> None:
    """Return to the previous wizard step."""

    st.session_state[StateKeys.STEP] = max(
        0, st.session_state.get(StateKeys.STEP, 0) - 1
    )


def on_file_uploaded() -> None:
    """Handle file uploads and populate job description text."""

    f = st.session_state.get(UIKeys.JD_FILE_UPLOADER)
    if not f:
        return
    try:
        txt = extract_text_from_file(f)
    except Exception as e:  # pragma: no cover - defensive
        display_error(
            tr(
                "Datei konnte nicht gelesen werden – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Failed to read file – you can also enter the information manually in the following steps.",
            ),
            str(e),
        )
        return
    if not txt.strip():
        display_error(
            tr(
                "Datei enthält keinen Text – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "File contains no text – you can also enter the information manually in the following steps.",
            ),
        )
        return
    st.session_state[StateKeys.RAW_TEXT] = txt
    st.session_state[UIKeys.JD_TEXT_INPUT] = txt


def on_url_changed() -> None:
    """Fetch text from URL and populate job description text."""

    url = st.session_state.get(UIKeys.JD_URL_INPUT, "").strip()
    if not url:
        return
    if not re.match(r"^https?://[\w./-]+$", url):
        display_error(
            tr(
                "Ungültige URL – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Invalid URL – you can also enter the information manually in the following steps.",
            )
        )
        return
    try:
        txt = extract_text_from_url(url)
    except Exception as e:  # pragma: no cover - defensive
        display_error(
            tr(
                "URL konnte nicht geladen werden – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Failed to fetch URL – you can also enter the information manually in the following steps.",
            ),
            str(e),
        )
        return
    if not txt or not txt.strip():
        display_error(
            tr(
                "Keine Textinhalte gefunden – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "No text content found – you can also enter the information manually in the following steps.",
            ),
        )
        return
    st.session_state[StateKeys.RAW_TEXT] = txt
    st.session_state[UIKeys.JD_TEXT_INPUT] = txt


def _autodetect_lang(text: str) -> None:
    """Detect language from ``text`` and set session state if default."""

    if (
        "lang_auto" in st.session_state
        or st.session_state.get("lang") != "de"
        or not text
    ):
        return
    try:
        from langdetect import detect

        if detect(text).startswith("en"):
            st.session_state["lang"] = "en"
    except Exception:  # pragma: no cover - best effort
        pass
    st.session_state["lang_auto"] = True


# Mapping from schema field paths to wizard section numbers
FIELD_SECTION_MAP = {
    "company.name": 1,
    "position.job_title": 1,
    "position.role_summary": 2,
    "location.country": 2,
    "requirements.hard_skills_required": 3,
    "requirements.soft_skills_required": 3,
}


def get_missing_critical_fields(*, max_section: int | None = None) -> list[str]:
    """Return critical fields missing from ``st.session_state``.

    Args:
        max_section: Optional highest section number to inspect.

    Returns:
        List of missing critical field paths.
    """

    missing: list[str] = []
    for field in CRITICAL_FIELDS:
        if max_section is not None and FIELD_SECTION_MAP.get(field, 0) > max_section:
            continue
        if not st.session_state.get(field):
            missing.append(field)

    for q in st.session_state.get("followup_questions", []):
        if q.get("priority") == "critical":
            missing.append(q.get("field", ""))
    return missing


# --- Hilfsfunktionen: Dot-Notation lesen/schreiben ---
def set_in(d: dict, path: str, value) -> None:
    """Assign a value in a nested dict via dot-separated path."""

    cur = d
    parts = path.split(".")
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def get_in(d: dict, path: str, default=None):
    """Retrieve a value from a nested dict via dot-separated path."""

    cur = d
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur


def _clear_generated() -> None:
    """Remove cached generated outputs from ``st.session_state``."""

    for key in (
        StateKeys.JOB_AD_MD,
        StateKeys.BOOLEAN_STR,
        StateKeys.INTERVIEW_GUIDE_MD,
    ):
        st.session_state.pop(key, None)


def _update_profile(path: str, value) -> None:
    """Update profile data and clear derived outputs if changed."""

    data = st.session_state[StateKeys.PROFILE]
    if get_in(data, path) != value:
        set_in(data, path, value)
        _clear_generated()


def render_followups_for(fields: list[str]) -> None:
    """Render follow-up questions for the given ``fields`` and update state."""

    remaining: list[dict] = []
    for q in st.session_state.get("followup_questions", []):
        field = q.get("field")
        if field not in fields:
            remaining.append(q)
            continue
        question = q.get("question", "")
        prefill = q.get("prefill", "")
        if q.get("priority") == "critical":
            st.markdown(
                "<span style='color:red'>*</span> " + question,
                unsafe_allow_html=True,
            )
            answer = st.text_input("", value=prefill, key=field)
        else:
            answer = st.text_input(question, value=prefill, key=field)
        st.session_state[field] = answer
    st.session_state["followup_questions"] = remaining


def flatten(d: dict, prefix: str = "") -> dict:
    """Convert a nested dict into dot-separated keys.

    Args:
        d: Dictionary to flatten.
        prefix: Prefix for generated keys.

    Returns:
        A new dictionary with flattened keys.
    """

    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def missing_keys(data: dict, critical: List[str]) -> List[str]:
    """Identify required keys that are missing or empty.

    Args:
        data: Vacancy data to inspect.
        critical: List of required dot-separated keys.

    Returns:
        List of keys that are absent or have empty values.
    """

    flat = flatten(data)
    return [k for k in critical if (k not in flat) or (flat[k] in (None, "", [], {}))]


# --- UI-Komponenten ---
def _chip_multiselect(label: str, options: List[str], values: List[str]) -> List[str]:
    """Render a multiselect component with stable keys.

    Args:
        label: UI label for the widget.
        options: Available options.
        values: Initially selected options.

    Returns:
        The list of selections from the user.
    """

    # Einfache, robuste Multiselect-Variante
    return st.multiselect(label, options=options, default=values, key=f"ms_{label}")


# --- Step-Renderers ---
def _step_intro():
    """Render the introductory step of the wizard.

    Returns:
        None
    """
    lang_labels = {"Deutsch": "de", "English": "en"}
    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = (
            "Deutsch" if st.session_state.get("lang", "de") == "de" else "English"
        )

    def _on_lang_change() -> None:
        st.session_state["lang"] = lang_labels[st.session_state[UIKeys.LANG_SELECT]]

    st.radio(
        "🌐 Sprache / Language",
        list(lang_labels.keys()),
        key=UIKeys.LANG_SELECT,
        horizontal=True,
        on_change=_on_lang_change,
    )

    st.header(
        tr("Willkommen zum Recruiting-Wizard", "Welcome to the Recruiting Wizard")
    )
    st.write(
        tr(
            (
                "Dieser Wizard hilft Ihnen, alle relevanten Stellenanforderungen zu sammeln und aufzubereiten. "
                "Am Ende erhalten Sie ein strukturiertes Profil Ihrer Vakanz."
            ),
            (
                "This wizard helps you collect and organize all relevant job requirements. "
                "In the end, you'll receive a structured profile of your vacancy."
            ),
        )
    )
    st.subheader(t("intro_title", st.session_state.lang))
    st.write(
        tr(
            (
                "Spare Zeit, Nerven und Geld, vermeide Informationsverlust im ersten Schritt eines jeden "
                "Recruiting-Prozesses und starte durch Bereitstellung einer Stellenanzeige den auf minimalen "
                "Input ausgelegten Informationsgewinnungsprozess."
            ),
            (
                "Save time, nerves, and money, avoid information loss in the first step of any recruiting "
                "process, and kick off the information-gathering process designed for minimal input by "
                "providing a job posting."
            ),
        )
    )
    st.markdown("#### " + tr("Vorteile", "Advantages"))
    advantages_md = tr(
        (
            "- Schnellere, vollständigere Anforderungsaufnahme\n"
            "- ESCO-gestützte Skill-Vervollständigung\n"
            "- Strukturierte Daten → bessere Suche & Matching\n"
            "- Klarere Ausschreibungen → bessere Candidate Experience"
        ),
        (
            "- Faster, more complete requirements capture\n"
            "- ESCO-assisted skill completion\n"
            "- Structured data → better search & matching\n"
            "- Clearer job ads → better candidate experience"
        ),
    )
    st.markdown(advantages_md)


def _step_source(schema: dict) -> None:
    """Render the source step where users choose text, file, or URL."""

    st.subheader(t("source", st.session_state.lang))
    st.caption(
        tr(
            "Stellenbeschreibung laden oder diesen Schritt überspringen, um Daten manuell einzugeben.",
            "Load a job description or skip to enter data manually.",
        )
    )
    tab_text, tab_file, tab_url = st.tabs(
        [tr("Text", "Text"), tr("Datei", "File"), tr("URL", "URL")]
    )

    with tab_text:
        bind_textarea(
            tr("Jobtext", "Job text"),
            UIKeys.JD_TEXT_INPUT,
            StateKeys.RAW_TEXT,
            placeholder=tr(
                "Bitte JD-Text einfügen oder Datei/URL wählen...",
                "Paste JD text here or upload a file / enter URL...",
            ),
            help=tr(
                "Fügen Sie den reinen Text Ihrer Stellenanzeige ein.",
                "Paste the plain text of your job posting.",
            ),
        )

    with tab_file:
        st.file_uploader(
            tr("JD hochladen (PDF/DOCX/TXT)", "Upload JD (PDF/DOCX/TXT)"),
            type=["pdf", "docx", "txt"],
            key=UIKeys.JD_FILE_UPLOADER,
            on_change=on_file_uploaded,
            help=tr(
                "Unterstützte Formate: PDF, DOCX oder TXT.",
                "Supported formats: PDF, DOCX or TXT.",
            ),
        )

    with tab_url:
        st.text_input(
            tr("oder eine Job-URL eingeben", "or enter a Job URL"),
            key=UIKeys.JD_URL_INPUT,
            on_change=on_url_changed,
            placeholder="https://example.com/job",
            help=tr(
                "Die Seite muss öffentlich erreichbar sein.",
                "The page must be publicly accessible.",
            ),
        )

    text_for_extract = st.session_state.get(StateKeys.RAW_TEXT, "").strip()
    analyze_clicked = st.button(t("analyze", st.session_state.lang), type="primary")
    skip_clicked = st.button(tr("Ohne Vorlage fortfahren", "Continue without template"))
    if analyze_clicked:
        if not text_for_extract:
            st.warning(
                tr(
                    "Keine Daten erkannt – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                    "No data detected – you can also enter the information manually in the following steps.",
                )
            )
        else:
            _autodetect_lang(text_for_extract)
            try:
                extracted = extract_with_function(
                    text_for_extract, schema, model=st.session_state.model
                )
                profile = NeedAnalysisProfile.model_validate(extracted)
                st.session_state[StateKeys.PROFILE] = profile.model_dump()
                title = profile.position.job_title or ""
                occ = (
                    search_occupation(title, st.session_state.lang or "en")
                    if title
                    else None
                )
                if occ:
                    profile.position.occupation_label = occ.get("preferredLabel") or ""
                    profile.position.occupation_uri = occ.get("uri") or ""
                    profile.position.occupation_group = occ.get("group") or ""
                    skills = enrich_skills(
                        occ.get("uri") or "",
                        st.session_state.lang or "en",
                    )
                    current_skills = set(
                        profile.requirements.hard_skills_required or []
                    )
                    merged = sorted(current_skills.union(skills or []))
                    profile.requirements.hard_skills_required = merged
                st.session_state[StateKeys.PROFILE] = profile.model_dump()
                summary = {}
                if profile.position.job_title:
                    summary[tr("Jobtitel", "Job title")] = profile.position.job_title
                if profile.company.name:
                    summary[tr("Firma", "Company")] = profile.company.name
                if profile.location.primary_city:
                    summary[tr("Ort", "Location")] = profile.location.primary_city
                st.session_state[StateKeys.EXTRACTION_SUMMARY] = summary
                # If Auto-reask is enabled, generate follow-up questions now
                if st.session_state.get("auto_reask"):
                    try:
                        payload = {
                            "data": profile.model_dump(),
                            "lang": st.session_state.lang,
                        }
                        followup_res = ask_followups(
                            payload,
                            model=st.session_state.model,
                            vector_store_id=st.session_state.vector_store_id or None,
                        )
                        st.session_state[StateKeys.FOLLOWUPS] = followup_res.get(
                            "questions", []
                        )
                    except Exception:
                        st.warning(
                            tr(
                                "Konnte keine Anschlussfragen erzeugen.",
                                "Could not generate follow-ups automatically.",
                            )
                        )
            except Exception as e:
                display_error(
                    tr("Extraktion fehlgeschlagen", "Extraction failed"),
                    str(e),
                )
    if skip_clicked:
        st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
        st.session_state[StateKeys.RAW_TEXT] = ""
        st.session_state[UIKeys.JD_TEXT_INPUT] = ""
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
        st.session_state[StateKeys.STEP] = 2
        st.rerun()
    summary_data = st.session_state.get(StateKeys.EXTRACTION_SUMMARY, {})
    if summary_data:
        st.success(
            tr(
                "Analyse abgeschlossen. Folgende Felder wurden automatisch ausgefüllt:",
                "Analysis complete. The following fields were auto-filled:",
            )
        )
        for label, value in summary_data.items():
            st.write(f"- {label}: {value}")
        if st.button(tr("Weiter", "Continue"), type="primary"):
            st.session_state[StateKeys.STEP] = 2
            st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
            st.rerun()


def _step_company():
    """Render the company information step.

    Returns:
        None
    """

    st.subheader(tr("Unternehmen", "Company"))
    st.caption(
        tr(
            "Basisinformationen zum Unternehmen angeben.",
            "Provide basic information about the company.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    data["company"]["name"] = st.text_input(
        tr("Firma *", "Company *"),
        value=data["company"].get("name", ""),
        placeholder=tr("z. B. ACME GmbH", "e.g., ACME Corp"),
        help=tr("Offizieller Firmenname", "Official company name"),
    )

    c1, c2, c3 = st.columns(3)
    data["company"]["brand_name"] = c1.text_input(
        tr("Marke/Tochterunternehmen", "Brand/Subsidiary"),
        value=data["company"].get("brand_name", ""),
        placeholder=tr("z. B. ACME Robotics", "e.g., ACME Robotics"),
    )
    data["company"]["industry"] = c2.text_input(
        tr("Branche", "Industry"),
        value=data["company"].get("industry", ""),
        placeholder=tr("z. B. IT-Services", "e.g., IT services"),
    )

    c3, c4 = st.columns(2)
    data["company"]["hq_location"] = c3.text_input(
        tr("Hauptsitz", "Headquarters"),
        value=data["company"].get("hq_location", ""),
        placeholder=tr("z. B. Berlin, DE", "e.g., Berlin, DE"),
    )
    data["company"]["size"] = c4.text_input(
        tr("Größe", "Size"),
        value=data["company"].get("size", ""),
        placeholder=tr("z. B. 50-100", "e.g., 50-100"),
    )

    with st.expander(tr("Weitere Unternehmensdetails", "Additional company details")):
        c5, c6 = st.columns(2)
        data["company"]["website"] = c5.text_input(
            tr("Website", "Website"),
            value=data["company"].get("website", ""),
            placeholder="https://example.com",
        )
        data["company"]["mission"] = c6.text_input(
            tr("Mission", "Mission"),
            value=data["company"].get("mission", ""),
            placeholder=tr(
                "z. B. Nachhaltige Mobilität fördern",
                "e.g., Promote sustainable mobility",
            ),
        )

        data["company"]["culture"] = st.text_area(
            tr("Kultur", "Culture"),
            value=data["company"].get("culture", ""),
            placeholder=tr(
                "z. B. flache Hierarchien, Remote-First",
                "e.g., flat hierarchies, remote-first",
            ),
        )

        st.markdown("---")
        st.markdown(tr("Kontakt", "Contact"))
        c7, c8 = st.columns(2)
        data["company"]["contact_name"] = c7.text_input(
            tr("Ansprechpartner", "Contact Name"),
            value=data["company"].get("contact_name", ""),
            placeholder=tr("z. B. Max Mustermann", "e.g., Jane Doe"),
        )
        data["company"]["contact_email"] = c8.text_input(
            tr("Kontakt-E-Mail", "Contact Email"),
            value=data["company"].get("contact_email", ""),
            placeholder="email@example.com",
        )
        data["company"]["contact_phone"] = st.text_input(
            tr("Kontakt-Telefon", "Contact Phone"),
            value=data["company"].get("contact_phone", ""),
            placeholder="+49 30 1234567",
        )

    # Inline follow-up questions for Company section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("company."):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _render_stakeholders(process: dict, key_prefix: str) -> None:
    """Render stakeholder inputs and update ``process`` in place."""

    stakeholders = process.setdefault(
        "stakeholders",
        [
            {
                "name": "",
                "role": "",
                "email": "",
                "primary": True,
            }
        ],
    )
    if st.button(
        tr("+ weiteren Stakeholder hinzufügen", "+ add stakeholder"),
        key=f"{key_prefix}.add",
    ):
        stakeholders.append({"name": "", "role": "", "email": "", "primary": False})

    for idx, person in enumerate(stakeholders):
        c1, c2, c3 = st.columns([2, 2, 3])
        person["name"] = c1.text_input(
            tr("Name", "Name"),
            value=person.get("name", ""),
            key=f"{key_prefix}.{idx}.name",
        )
        person["role"] = c2.text_input(
            tr("Funktion/Rolle", "Role"),
            value=person.get("role", ""),
            key=f"{key_prefix}.{idx}.role",
        )
        person["email"] = c3.text_input(
            "E-Mail",
            value=person.get("email", ""),
            key=f"{key_prefix}.{idx}.email",
        )

    primary_idx = st.radio(
        tr("Primärer Kontakt", "Primary contact"),
        options=list(range(len(stakeholders))),
        index=next((i for i, p in enumerate(stakeholders) if p.get("primary")), 0),
        format_func=lambda i: stakeholders[i].get("name") or f"#{i + 1}",
        key=f"{key_prefix}.primary",
    )
    for i, p in enumerate(stakeholders):
        p["primary"] = i == primary_idx


def _render_phases(process: dict, stakeholders: list[dict], key_prefix: str) -> None:
    """Render phase inputs based on ``interview_stages``."""

    phases = process.setdefault("phases", [])
    stages = st.number_input(
        tr("Phasen", "Stages"),
        value=len(phases),
        key=f"{key_prefix}.count",
        min_value=0,
    )
    process["interview_stages"] = int(stages)

    while len(phases) < stages:
        phases.append(
            {
                "name": "",
                "interview_format": "phone",
                "participants": [],
                "docs_required": "",
                "assessment_tests": False,
                "timeframe": "",
            }
        )
    while len(phases) > stages:
        phases.pop()

    format_options = [
        ("phone", tr("Telefon", "Phone")),
        ("video", tr("Videocall", "Video call")),
        ("on_site", tr("Vor Ort", "On-site")),
        ("other", tr("Sonstiges", "Other")),
    ]

    stakeholder_names = [s.get("name", "") for s in stakeholders if s.get("name")]

    for idx, phase in enumerate(phases):
        with st.expander(f"{tr('Phase', 'Phase')} {idx + 1}", expanded=True):
            phase["name"] = st.text_input(
                tr("Phasen-Name", "Phase name"),
                value=phase.get("name", ""),
                key=f"{key_prefix}.{idx}.name",
            )
            value_options = [v for v, _ in format_options]
            format_index = (
                value_options.index(phase.get("interview_format", "phone"))
                if phase.get("interview_format") in value_options
                else 0
            )
            phase["interview_format"] = st.selectbox(
                tr("Interview-Format", "Interview format"),
                options=value_options,
                index=format_index,
                format_func=dict(format_options).__getitem__,
                key=f"{key_prefix}.{idx}.format",
            )
            phase["participants"] = st.multiselect(
                tr("Beteiligte", "Participants"),
                stakeholder_names,
                default=phase.get("participants", []),
                key=f"{key_prefix}.{idx}.participants",
            )
            phase["docs_required"] = st.text_input(
                tr("Benötigte Unterlagen/Assignments", "Required docs/assignments"),
                value=phase.get("docs_required", ""),
                key=f"{key_prefix}.{idx}.docs",
            )
            phase["assessment_tests"] = st.checkbox(
                tr("Assessment/Test", "Assessment/test"),
                value=phase.get("assessment_tests", False),
                key=f"{key_prefix}.{idx}.assessment",
            )
            phase["timeframe"] = st.text_input(
                tr("Geplanter Zeitrahmen", "Timeframe"),
                value=phase.get("timeframe", ""),
                key=f"{key_prefix}.{idx}.timeframe",
            )


def _step_position():
    """Render the position details step.

    Returns:
        None
    """

    st.subheader(tr("Position", "Position"))
    st.caption(
        tr(
            "Details zur Rolle eingeben, z. B. Titel und Seniorität.",
            "Provide role details such as title and seniority.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    c1, c2, c3 = st.columns(3)
    data["position"]["job_title"] = c1.text_input(
        tr("Jobtitel *", "Job title *"),
        value=data["position"].get("job_title", ""),
        placeholder=tr("z. B. Data Scientist", "e.g., Data Scientist"),
    )
    data["position"]["seniority_level"] = c2.text_input(
        tr("Seniorität", "Seniority"),
        value=data["position"].get("seniority_level", ""),
        placeholder=tr("z. B. Junior", "e.g., Junior"),
    )

    c3, c4 = st.columns(2)
    data["position"]["department"] = c3.text_input(
        tr("Abteilung", "Department"),
        value=data["position"].get("department", ""),
        placeholder=tr("z. B. Entwicklung", "e.g., Engineering"),
    )
    data["position"]["team_structure"] = c4.text_input(
        tr("Teamstruktur", "Team structure"),
        value=data["position"].get("team_structure", ""),
        placeholder=tr(
            "z. B. 5 Personen, cross-funktional", "e.g., 5 people, cross-functional"
        ),
    )

    c5, c6 = st.columns(2)
    data["position"]["reporting_line"] = c5.text_input(
        tr("Reports an", "Reports to"),
        value=data["position"].get("reporting_line", ""),
        placeholder=tr("z. B. CTO", "e.g., CTO"),
    )
    data["position"]["role_summary"] = c6.text_area(
        tr("Rollen-Summary *", "Role summary *"),
        value=data["position"].get("role_summary", ""),
        height=120,
    )

    c7, c8 = st.columns(2)
    data["meta"]["target_start_date"] = c7.text_input(
        tr("Gewünschtes Startdatum", "Desired start date"),
        value=data["meta"].get("target_start_date", ""),
        placeholder="YYYY-MM-DD",
    )
    data["position"]["supervises"] = c8.number_input(
        tr("Anzahl unterstellter Mitarbeiter", "Direct reports"),
        min_value=0,
        value=data["position"].get("supervises", 0),
        step=1,
    )

    with st.expander(tr("Weitere Rollen-Details", "Additional role details")):
        data["position"]["performance_indicators"] = st.text_area(
            tr("Leistungskennzahlen", "Performance indicators"),
            value=data["position"].get("performance_indicators", ""),
            height=80,
        )
        data["position"]["decision_authority"] = st.text_area(
            tr("Entscheidungsbefugnisse", "Decision-making authority"),
            value=data["position"].get("decision_authority", ""),
            height=80,
        )
        data["position"]["key_projects"] = st.text_area(
            tr("Schlüsselprojekte", "Key projects"),
            value=data["position"].get("key_projects", ""),
            height=80,
        )

    # Inline follow-up questions for Position and Location section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if (
                field.startswith("position.")
                or field.startswith("location.")
                or field.startswith("meta.")
            ):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _step_requirements():
    """Render the requirements step for skills and certifications.

    Returns:
        None
    """

    st.subheader(tr("Anforderungen", "Requirements"))
    st.caption(
        tr(
            "Geforderte Fähigkeiten und Qualifikationen festhalten.",
            "Specify required skills and qualifications.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    # LLM-basierte Skill-Vorschläge abrufen
    job_title = (data.get("position", {}).get("job_title", "") or "").strip()
    stored = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})
    if job_title and stored.get("_title") != job_title:
        sugg = suggest_skills_for_role(
            job_title,
            lang=st.session_state.get("lang", "en"),
        )
        stored = {"_title": job_title, **sugg}
        st.session_state[StateKeys.SKILL_SUGGESTIONS] = stored
    suggestions = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})

    data["requirements"]["hard_skills_required"] = _chip_multiselect(
        "Hard Skills (Must-have)",
        options=data["requirements"].get("hard_skills_required", []),
        values=data["requirements"].get("hard_skills_required", []),
    )
    data["requirements"]["hard_skills_optional"] = _chip_multiselect(
        "Hard Skills (Nice-to-have)",
        options=data["requirements"].get("hard_skills_optional", []),
        values=data["requirements"].get("hard_skills_optional", []),
    )
    data["requirements"]["soft_skills_required"] = _chip_multiselect(
        "Soft Skills (Must-have)",
        options=data["requirements"].get("soft_skills_required", []),
        values=data["requirements"].get("soft_skills_required", []),
    )
    data["requirements"]["soft_skills_optional"] = _chip_multiselect(
        "Soft Skills (Nice-to-have)",
        options=data["requirements"].get("soft_skills_optional", []),
        values=data["requirements"].get("soft_skills_optional", []),
    )
    data["requirements"]["tools_and_technologies"] = _chip_multiselect(
        "Tools & Tech",
        options=data["requirements"].get("tools_and_technologies", []),
        values=data["requirements"].get("tools_and_technologies", []),
    )
    data["requirements"]["languages_required"] = _chip_multiselect(
        tr("Sprachen", "Languages"),
        options=data["requirements"].get("languages_required", []),
        values=data["requirements"].get("languages_required", []),
    )
    data["requirements"]["languages_optional"] = _chip_multiselect(
        tr("Optionale Sprachen", "Optional languages"),
        options=data["requirements"].get("languages_optional", []),
        values=data["requirements"].get("languages_optional", []),
    )
    data["requirements"]["certifications"] = _chip_multiselect(
        tr("Zertifizierungen", "Certifications"),
        options=data["requirements"].get("certifications", []),
        values=data["requirements"].get("certifications", []),
    )

    # Vorschlagslisten
    sugg_tools = st.multiselect(
        tr("Vorgeschlagene Tools & Tech", "Suggested Tools & Tech"),
        options=[
            s
            for s in suggestions.get("tools_and_technologies", [])
            if s not in data["requirements"].get("tools_and_technologies", [])
        ],
        key="ms_sugg_tools",
    )
    if sugg_tools:
        merged = sorted(
            set(data["requirements"].get("tools_and_technologies", [])).union(
                sugg_tools
            )
        )
        data["requirements"]["tools_and_technologies"] = merged

    sugg_hard = st.multiselect(
        tr("Vorgeschlagene Hard Skills", "Suggested Hard Skills"),
        options=[
            s
            for s in suggestions.get("hard_skills", [])
            if s not in data["requirements"].get("hard_skills_required", [])
        ],
        key="ms_sugg_hard",
    )
    if sugg_hard:
        merged = sorted(
            set(data["requirements"].get("hard_skills_required", [])).union(sugg_hard)
        )
        data["requirements"]["hard_skills_required"] = merged

    sugg_soft = st.multiselect(
        tr("Vorgeschlagene Soft Skills", "Suggested Soft Skills"),
        options=[
            s
            for s in suggestions.get("soft_skills", [])
            if s not in data["requirements"].get("soft_skills_required", [])
        ],
        key="ms_sugg_soft",
    )
    if sugg_soft:
        merged = sorted(
            set(data["requirements"].get("soft_skills_required", [])).union(sugg_soft)
        )
        data["requirements"]["soft_skills_required"] = merged

    # Inline follow-up questions for Requirements section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("requirements."):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _step_employment():
    """Render the employment details step.

    Returns:
        None
    """

    st.subheader(tr("Beschäftigung", "Employment"))
    st.caption(
        tr(
            "Rahmenbedingungen der Anstellung festlegen.",
            "Define employment conditions.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    c1, c2, c3 = st.columns(3)
    job_options = [
        "full_time",
        "part_time",
        "contract",
        "internship",
        "temporary",
        "other",
    ]
    current_job = data["employment"].get("job_type")
    data["employment"]["job_type"] = c1.selectbox(
        tr("Art", "Type"),
        options=job_options,
        index=job_options.index(current_job) if current_job in job_options else 0,
    )
    policy_options = ["onsite", "hybrid", "remote"]
    current_policy = data["employment"].get("work_policy")
    data["employment"]["work_policy"] = c2.selectbox(
        tr("Policy", "Policy"),
        options=policy_options,
        index=(
            policy_options.index(current_policy)
            if current_policy in policy_options
            else 0
        ),
    )

    contract_options = {
        "permanent": tr("Unbefristet", "Permanent"),
        "fixed_term": tr("Befristet", "Fixed term"),
        "contract": tr("Werkvertrag", "Contract"),
        "other": tr("Sonstiges", "Other"),
    }
    current_contract = data["employment"].get("contract_type")
    data["employment"]["contract_type"] = c3.selectbox(
        tr("Vertragsart", "Contract type"),
        options=list(contract_options.keys()),
        format_func=lambda x: contract_options[x],
        index=(
            list(contract_options.keys()).index(current_contract)
            if current_contract in contract_options
            else 0
        ),
    )

    schedule_options = {
        "standard": tr("Standard", "Standard"),
        "flexitime": tr("Gleitzeit", "Flexitime"),
        "shift": tr("Schichtarbeit", "Shift work"),
        "weekend": tr("Wochenendarbeit", "Weekend work"),
        "other": tr("Sonstiges", "Other"),
    }
    current_schedule = data["employment"].get("work_schedule")
    data["employment"]["work_schedule"] = st.selectbox(
        tr("Arbeitszeitmodell", "Work schedule"),
        options=list(schedule_options.keys()),
        format_func=lambda x: schedule_options[x],
        index=(
            list(schedule_options.keys()).index(current_schedule)
            if current_schedule in schedule_options
            else 0
        ),
    )

    if data["employment"].get("work_policy") in ["hybrid", "remote"]:
        data["employment"]["remote_percentage"] = st.number_input(
            tr("Remote-Anteil (%)", "Remote share (%)"),
            min_value=0,
            max_value=100,
            value=int(data["employment"].get("remote_percentage") or 0),
        )
    else:
        data["employment"].pop("remote_percentage", None)

    if data["employment"].get("contract_type") == "fixed_term":
        contract_end_str = data["employment"].get("contract_end")
        default_end = (
            date.fromisoformat(contract_end_str) if contract_end_str else date.today()
        )
        data["employment"]["contract_end"] = st.date_input(
            tr("Vertragsende", "Contract end"),
            value=default_end,
        ).isoformat()
    else:
        data["employment"].pop("contract_end", None)

    c4, c5, c6 = st.columns(3)
    data["employment"]["travel_required"] = c4.toggle(
        tr("Reisetätigkeit?", "Travel required?"),
        value=bool(data["employment"].get("travel_required")),
    )
    data["employment"]["relocation_support"] = c5.toggle(
        tr("Relocation?", "Relocation?"),
        value=bool(data["employment"].get("relocation_support")),
    )
    data["employment"]["visa_sponsorship"] = c6.toggle(
        tr("Visum-Sponsoring?", "Visa sponsorship?"),
        value=bool(data["employment"].get("visa_sponsorship")),
    )

    if data["employment"].get("travel_required"):
        data["employment"]["travel_details"] = st.text_input(
            tr("Reisedetails", "Travel details"),
            value=data["employment"].get("travel_details", ""),
        )
    else:
        data["employment"].pop("travel_details", None)

    if data["employment"].get("relocation_support"):
        data["employment"]["relocation_details"] = st.text_input(
            tr("Umzugsunterstützung", "Relocation details"),
            value=data["employment"].get("relocation_details", ""),
        )
    else:
        data["employment"].pop("relocation_details", None)

    # Inline follow-up questions for Employment section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("employment."):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _step_compensation():
    """Render the compensation and benefits step.

    Returns:
        None
    """

    st.subheader(tr("Vergütung & Benefits", "Compensation & Benefits"))
    st.caption(
        tr(
            "Gehaltsspanne und Zusatzleistungen erfassen.",
            "Capture salary range and benefits.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    salary_min = float(data["compensation"].get("salary_min") or 0.0)
    salary_max = float(data["compensation"].get("salary_max") or 0.0)
    salary_min, salary_max = st.slider(
        tr("Gehaltsspanne", "Salary range"),
        min_value=0.0,
        max_value=500000.0,
        value=(salary_min, salary_max),
        step=1000.0,
    )
    data["compensation"]["salary_min"] = salary_min
    data["compensation"]["salary_max"] = salary_max

    c1, c2, c3 = st.columns(3)
    currency_options = ["EUR", "USD", "CHF", "GBP", "Other"]
    current_currency = data["compensation"].get("currency", "EUR")
    idx = (
        currency_options.index(current_currency)
        if current_currency in currency_options
        else currency_options.index("Other")
    )
    choice = c1.selectbox(
        tr("Währung", "Currency"), options=currency_options, index=idx
    )
    if choice == "Other":
        data["compensation"]["currency"] = c1.text_input(
            tr("Andere Währung", "Other currency"),
            value=("" if current_currency in currency_options else current_currency),
        )
    else:
        data["compensation"]["currency"] = choice

    period_options = ["year", "month", "day", "hour"]
    current_period = data["compensation"].get("period")
    data["compensation"]["period"] = c2.selectbox(
        tr("Periode", "Period"),
        options=period_options,
        index=(
            period_options.index(current_period)
            if current_period in period_options
            else 0
        ),
    )
    data["compensation"]["variable_pay"] = c3.toggle(
        tr("Variable Vergütung?", "Variable pay?"),
        value=bool(data["compensation"].get("variable_pay")),
    )

    if data["compensation"]["variable_pay"]:
        c4, c5 = st.columns(2)
        data["compensation"]["bonus_percentage"] = c4.number_input(
            tr("Bonus %", "Bonus %"),
            min_value=0.0,
            max_value=100.0,
            value=float(data["compensation"].get("bonus_percentage") or 0.0),
        )
        data["compensation"]["commission_structure"] = c5.text_input(
            tr("Provisionsmodell", "Commission structure"),
            value=data["compensation"].get("commission_structure", ""),
        )

    c6, c7 = st.columns(2)
    data["compensation"]["equity_offered"] = c6.toggle(
        "Equity?", value=bool(data["compensation"].get("equity_offered"))
    )
    lang = st.session_state.get("lang", "de")
    preset_benefits = {
        "de": [
            "Firmenwagen",
            "Home-Office",
            "Weiterbildungsbudget",
            "Betriebliche Altersvorsorge",
            "Team-Events",
        ],
        "en": [
            "Company car",
            "Home office",
            "Training budget",
            "Pension plan",
            "Team events",
        ],
    }
    benefit_options = sorted(
        set(preset_benefits.get(lang, []) + data["compensation"].get("benefits", []))
    )
    data["compensation"]["benefits"] = _chip_multiselect(
        "Benefits",
        options=benefit_options,
        values=data["compensation"].get("benefits", []),
    )

    # Inline follow-up questions for Compensation section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("compensation."):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _step_process():
    """Render the hiring process step."""

    st.subheader(tr("Prozess", "Process"))
    st.caption(
        tr(
            "Ablauf des Bewerbungsprozesses skizzieren.",
            "Outline the hiring process steps.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]["process"]

    _render_stakeholders(data, "ui.process.stakeholders")
    _render_phases(data, data.get("stakeholders", []), "ui.process.phases")

    c1, c2 = st.columns(2)
    data["recruitment_timeline"] = c1.text_area(
        tr("Gesamt-Timeline", "Overall timeline"),
        value=data.get("recruitment_timeline", ""),
        key="ui.process.recruitment_timeline",
    )
    data["process_notes"] = c2.text_area(
        tr("Notizen", "Notes"),
        value=data.get("process_notes", ""),
        key="ui.process.notes",
    )
    data["application_instructions"] = st.text_area(
        tr("Bewerbungsinstruktionen", "Application instructions"),
        value=data.get("application_instructions", ""),
        key="ui.process.application_instructions",
    )
    with st.expander(tr("Onboarding (nach Einstellung)", "Onboarding (post-hire)")):
        data["onboarding_process"] = st.text_area(
            tr("Onboarding-Prozess", "Onboarding process"),
            value=data.get("onboarding_process", ""),
            key="ui.process.onboarding_process",
        )

    # Inline follow-up questions for Process section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("process."):
                prompt = q.get("question", "")
                if q.get("priority") == "critical":
                    st.markdown(
                        f"<span style='color:red'>*</span> **{prompt}**",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{prompt}**")
                ans = st.text_input("", key=f"fu_{field}")
                if ans:
                    set_in(st.session_state[StateKeys.PROFILE], field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _summary_company() -> None:
    """Editable summary tab for company information."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    name = c1.text_input(
        tr("Firma *", "Company *"),
        value=data["company"].get("name", ""),
        key="ui.summary.company.name",
    )
    industry = c2.text_input(
        tr("Branche", "Industry"),
        value=data["company"].get("industry", ""),
        key="ui.summary.company.industry",
    )
    hq = c1.text_input(
        tr("Hauptsitz", "Headquarters"),
        value=data["company"].get("hq_location", ""),
        key="ui.summary.company.hq_location",
    )
    size = c2.text_input(
        tr("Größe", "Size"),
        value=data["company"].get("size", ""),
        key="ui.summary.company.size",
    )
    website = c1.text_input(
        tr("Website", "Website"),
        value=data["company"].get("website", ""),
        key="ui.summary.company.website",
    )
    mission = c2.text_input(
        tr("Mission", "Mission"),
        value=data["company"].get("mission", ""),
        key="ui.summary.company.mission",
    )
    culture = st.text_area(
        tr("Kultur", "Culture"),
        value=data["company"].get("culture", ""),
        key="ui.summary.company.culture",
    )

    _update_profile("company.name", name)
    _update_profile("company.industry", industry)
    _update_profile("company.hq_location", hq)
    _update_profile("company.size", size)
    _update_profile("company.website", website)
    _update_profile("company.mission", mission)
    _update_profile("company.culture", culture)


def _summary_position() -> None:
    """Editable summary tab for position details."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    job_title = c1.text_input(
        tr("Jobtitel *", "Job title *"),
        value=data["position"].get("job_title", ""),
        key="ui.summary.position.job_title",
    )
    seniority = c2.text_input(
        tr("Seniorität", "Seniority"),
        value=data["position"].get("seniority_level", ""),
        key="ui.summary.position.seniority",
    )
    department = c1.text_input(
        tr("Abteilung", "Department"),
        value=data["position"].get("department", ""),
        key="ui.summary.position.department",
    )
    team = c2.text_input(
        tr("Teamstruktur", "Team structure"),
        value=data["position"].get("team_structure", ""),
        key="ui.summary.position.team_structure",
    )
    reporting = c1.text_input(
        tr("Reports an", "Reports to"),
        value=data["position"].get("reporting_line", ""),
        key="ui.summary.position.reporting_line",
    )
    role_summary = c2.text_area(
        tr("Rollen-Summary *", "Role summary *"),
        value=data["position"].get("role_summary", ""),
        height=120,
        key="ui.summary.position.role_summary",
    )
    loc_city = c1.text_input(
        tr("Stadt", "City"),
        value=data.get("location", {}).get("primary_city", ""),
        key="ui.summary.location.primary_city",
    )
    loc_country = c2.text_input(
        tr("Land", "Country"),
        value=data.get("location", {}).get("country", ""),
        key="ui.summary.location.country",
    )

    _update_profile("position.job_title", job_title)
    _update_profile("position.seniority_level", seniority)
    _update_profile("position.department", department)
    _update_profile("position.team_structure", team)
    _update_profile("position.reporting_line", reporting)
    _update_profile("position.role_summary", role_summary)
    _update_profile("location.primary_city", loc_city)
    _update_profile("location.country", loc_country)


def _summary_requirements() -> None:
    """Editable summary tab for requirements."""

    data = st.session_state[StateKeys.PROFILE]

    hard_req = st.text_area(
        "Hard Skills (Must-have)",
        value=", ".join(data["requirements"].get("hard_skills_required", [])),
        key="ui.summary.requirements.hard_skills_required",
    )
    hard_opt = st.text_area(
        "Hard Skills (Nice-to-have)",
        value=", ".join(data["requirements"].get("hard_skills_optional", [])),
        key="ui.summary.requirements.hard_skills_optional",
    )
    soft_req = st.text_area(
        "Soft Skills (Must-have)",
        value=", ".join(data["requirements"].get("soft_skills_required", [])),
        key="ui.summary.requirements.soft_skills_required",
    )
    soft_opt = st.text_area(
        "Soft Skills (Nice-to-have)",
        value=", ".join(data["requirements"].get("soft_skills_optional", [])),
        key="ui.summary.requirements.soft_skills_optional",
    )
    tools = st.text_area(
        "Tools & Tech",
        value=", ".join(data["requirements"].get("tools_and_technologies", [])),
        key="ui.summary.requirements.tools",
    )
    languages_req = st.text_area(
        tr("Sprachen", "Languages"),
        value=", ".join(data["requirements"].get("languages_required", [])),
        key="ui.summary.requirements.languages_required",
    )
    languages_opt = st.text_area(
        tr("Optionale Sprachen", "Optional languages"),
        value=", ".join(data["requirements"].get("languages_optional", [])),
        key="ui.summary.requirements.languages_optional",
    )
    certs = st.text_area(
        tr("Zertifizierungen", "Certifications"),
        value=", ".join(data["requirements"].get("certifications", [])),
        key="ui.summary.requirements.certs",
    )

    _update_profile(
        "requirements.hard_skills_required",
        [s.strip() for s in hard_req.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.hard_skills_optional",
        [s.strip() for s in hard_opt.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.soft_skills_required",
        [s.strip() for s in soft_req.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.soft_skills_optional",
        [s.strip() for s in soft_opt.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.tools_and_technologies",
        [s.strip() for s in tools.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.languages_required",
        [s.strip() for s in languages_req.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.languages_optional",
        [s.strip() for s in languages_opt.split(",") if s.strip()],
    )
    _update_profile(
        "requirements.certifications",
        [s.strip() for s in certs.split(",") if s.strip()],
    )


def _summary_employment() -> None:
    """Editable summary tab for employment details."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    job_options = [
        "full_time",
        "part_time",
        "contract",
        "internship",
        "temporary",
        "other",
    ]
    job_type = c1.selectbox(
        tr("Art", "Type"),
        options=job_options,
        index=(
            job_options.index(data["employment"].get("job_type"))
            if data["employment"].get("job_type") in job_options
            else 0
        ),
        key="ui.summary.employment.job_type",
    )
    policy_options = ["onsite", "hybrid", "remote"]
    work_policy = c2.selectbox(
        tr("Policy", "Policy"),
        options=policy_options,
        index=(
            policy_options.index(data["employment"].get("work_policy"))
            if data["employment"].get("work_policy") in policy_options
            else 0
        ),
        key="ui.summary.employment.work_policy",
    )

    c3, c4 = st.columns(2)
    contract_options = {
        "permanent": tr("Unbefristet", "Permanent"),
        "fixed_term": tr("Befristet", "Fixed term"),
        "contract": tr("Werkvertrag", "Contract"),
        "other": tr("Sonstiges", "Other"),
    }
    contract_type = c3.selectbox(
        tr("Vertragsart", "Contract type"),
        options=list(contract_options.keys()),
        format_func=lambda x: contract_options[x],
        index=(
            list(contract_options.keys()).index(data["employment"].get("contract_type"))
            if data["employment"].get("contract_type") in contract_options
            else 0
        ),
        key="ui.summary.employment.contract_type",
    )
    schedule_options = {
        "standard": tr("Standard", "Standard"),
        "flexitime": tr("Gleitzeit", "Flexitime"),
        "shift": tr("Schichtarbeit", "Shift work"),
        "weekend": tr("Wochenendarbeit", "Weekend work"),
        "other": tr("Sonstiges", "Other"),
    }
    work_schedule = c4.selectbox(
        tr("Arbeitszeitmodell", "Work schedule"),
        options=list(schedule_options.keys()),
        format_func=lambda x: schedule_options[x],
        index=(
            list(schedule_options.keys()).index(data["employment"].get("work_schedule"))
            if data["employment"].get("work_schedule") in schedule_options
            else 0
        ),
        key="ui.summary.employment.work_schedule",
    )

    if work_policy in ["hybrid", "remote"]:
        remote_percentage = st.number_input(
            tr("Remote-Anteil (%)", "Remote share (%)"),
            min_value=0,
            max_value=100,
            value=int(data["employment"].get("remote_percentage") or 0),
            key="ui.summary.employment.remote_percentage",
        )
    else:
        remote_percentage = None

    if contract_type == "fixed_term":
        contract_end_str = data["employment"].get("contract_end")
        default_end = (
            date.fromisoformat(contract_end_str) if contract_end_str else date.today()
        )
        contract_end = st.date_input(
            tr("Vertragsende", "Contract end"),
            value=default_end,
            key="ui.summary.employment.contract_end",
        )
    else:
        contract_end = None

    c5, c6, c7 = st.columns(3)
    travel = c5.toggle(
        tr("Reisetätigkeit?", "Travel required?"),
        value=bool(data["employment"].get("travel_required")),
        key="ui.summary.employment.travel_required",
    )
    relocation = c6.toggle(
        tr("Relocation?", "Relocation?"),
        value=bool(data["employment"].get("relocation_support")),
        key="ui.summary.employment.relocation_support",
    )
    visa = c7.toggle(
        tr("Visum-Sponsoring?", "Visa sponsorship?"),
        value=bool(data["employment"].get("visa_sponsorship")),
        key="ui.summary.employment.visa_sponsorship",
    )

    if travel:
        travel_details = st.text_input(
            tr("Reisedetails", "Travel details"),
            value=data["employment"].get("travel_details", ""),
            key="ui.summary.employment.travel_details",
        )
    else:
        travel_details = None

    if relocation:
        relocation_details = st.text_input(
            tr("Umzugsunterstützung", "Relocation details"),
            value=data["employment"].get("relocation_details", ""),
            key="ui.summary.employment.relocation_details",
        )
    else:
        relocation_details = None

    _update_profile("employment.job_type", job_type)
    _update_profile("employment.work_policy", work_policy)
    _update_profile("employment.contract_type", contract_type)
    _update_profile("employment.work_schedule", work_schedule)
    _update_profile("employment.remote_percentage", remote_percentage)
    _update_profile(
        "employment.contract_end",
        contract_end.isoformat() if contract_end else None,
    )
    _update_profile("employment.travel_required", travel)
    _update_profile("employment.relocation_support", relocation)
    _update_profile("employment.visa_sponsorship", visa)
    _update_profile("employment.travel_details", travel_details)
    _update_profile("employment.relocation_details", relocation_details)


def _summary_compensation() -> None:
    """Editable summary tab for compensation details."""

    data = st.session_state[StateKeys.PROFILE]
    salary_min = float(data["compensation"].get("salary_min") or 0.0)
    salary_max = float(data["compensation"].get("salary_max") or 0.0)
    salary_min, salary_max = st.slider(
        tr("Gehaltsspanne", "Salary range"),
        min_value=0.0,
        max_value=500000.0,
        value=(salary_min, salary_max),
        step=1000.0,
        key="ui.summary.compensation.salary_range",
    )
    c1, c2, c3 = st.columns(3)
    currency_options = ["EUR", "USD", "CHF", "GBP", "Other"]
    current_currency = data["compensation"].get("currency", "EUR")
    idx = (
        currency_options.index(current_currency)
        if current_currency in currency_options
        else currency_options.index("Other")
    )
    choice = c1.selectbox(
        tr("Währung", "Currency"),
        options=currency_options,
        index=idx,
        key="ui.summary.compensation.currency_select",
    )
    if choice == "Other":
        currency = c1.text_input(
            tr("Andere Währung", "Other currency"),
            value=("" if current_currency in currency_options else current_currency),
            key="ui.summary.compensation.currency_other",
        )
    else:
        currency = choice
    period_options = ["year", "month", "day", "hour"]
    period = c2.selectbox(
        tr("Periode", "Period"),
        options=period_options,
        index=(
            period_options.index(data["compensation"].get("period"))
            if data["compensation"].get("period") in period_options
            else 0
        ),
        key="ui.summary.compensation.period",
    )
    variable = c3.toggle(
        tr("Variable Vergütung?", "Variable pay?"),
        value=bool(data["compensation"].get("variable_pay")),
        key="ui.summary.compensation.variable_pay",
    )
    if variable:
        c4, c5 = st.columns(2)
        bonus_percentage = c4.number_input(
            tr("Bonus %", "Bonus %"),
            min_value=0.0,
            max_value=100.0,
            value=float(data["compensation"].get("bonus_percentage") or 0.0),
            key="ui.summary.compensation.bonus_percentage",
        )
        commission_structure = c5.text_input(
            tr("Provisionsmodell", "Commission structure"),
            value=data["compensation"].get("commission_structure", ""),
            key="ui.summary.compensation.commission_structure",
        )
    else:
        bonus_percentage = data["compensation"].get("bonus_percentage")
        commission_structure = data["compensation"].get("commission_structure")

    c6, c7 = st.columns(2)
    equity = c6.toggle(
        "Equity?",
        value=bool(data["compensation"].get("equity_offered")),
        key="ui.summary.compensation.equity_offered",
    )
    lang = st.session_state.get("lang", "de")
    preset_benefits = {
        "de": [
            "Firmenwagen",
            "Home-Office",
            "Weiterbildungsbudget",
            "Betriebliche Altersvorsorge",
            "Team-Events",
        ],
        "en": [
            "Company car",
            "Home office",
            "Training budget",
            "Pension plan",
            "Team events",
        ],
    }
    benefit_options = sorted(
        set(preset_benefits.get(lang, []) + data["compensation"].get("benefits", []))
    )
    benefits = _chip_multiselect(
        "Benefits",
        options=benefit_options,
        values=data["compensation"].get("benefits", []),
    )

    _update_profile("compensation.salary_min", salary_min)
    _update_profile("compensation.salary_max", salary_max)
    _update_profile("compensation.currency", currency)
    _update_profile("compensation.period", period)
    _update_profile("compensation.variable_pay", variable)
    _update_profile("compensation.bonus_percentage", bonus_percentage)
    _update_profile("compensation.commission_structure", commission_structure)
    _update_profile("compensation.equity_offered", equity)
    _update_profile("compensation.benefits", benefits)


def _summary_process() -> None:
    """Editable summary tab for hiring process details."""

    process = st.session_state[StateKeys.PROFILE]["process"]

    _render_stakeholders(process, "ui.summary.process.stakeholders")
    _update_profile("process.stakeholders", process.get("stakeholders", []))

    _render_phases(
        process,
        process.get("stakeholders", []),
        "ui.summary.process.phases",
    )
    _update_profile("process.phases", process.get("phases", []))
    _update_profile(
        "process.interview_stages", int(process.get("interview_stages") or 0)
    )

    c1, c2 = st.columns(2)
    timeline = c1.text_area(
        tr("Gesamt-Timeline", "Overall timeline"),
        value=process.get("recruitment_timeline", ""),
        key="ui.summary.process.recruitment_timeline",
    )
    notes = c2.text_area(
        tr("Notizen", "Notes"),
        value=process.get("process_notes", ""),
        key="ui.summary.process.process_notes",
    )
    instructions = st.text_area(
        tr("Bewerbungsinstruktionen", "Application instructions"),
        value=process.get("application_instructions", ""),
        key="ui.summary.process.application_instructions",
    )
    with st.expander(tr("Onboarding (nach Einstellung)", "Onboarding (post-hire)")):
        onboarding = st.text_area(
            tr("Onboarding-Prozess", "Onboarding process"),
            value=process.get("onboarding_process", ""),
            key="ui.summary.process.onboarding_process",
        )

    _update_profile("process.recruitment_timeline", timeline)
    _update_profile("process.process_notes", notes)
    _update_profile("process.application_instructions", instructions)
    _update_profile("process.onboarding_process", onboarding)


def _step_summary(schema: dict, critical: list[str]):
    """Render the summary step and offer follow-up questions.

    Args:
        schema: Schema defining allowed fields.
        critical: Keys that must be present in ``data``.

    Returns:
        None
    """

    st.subheader(tr("Zusammenfassung", "Summary"))
    st.caption(
        tr(
            "Überprüfen Sie Ihre Angaben und laden Sie das Profil herunter.",
            "Review your entries and download the profile.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]
    missing = missing_keys(data, critical)
    if missing:
        st.warning(f"{t('missing', st.session_state.lang)} {', '.join(missing)}")

    tabs = st.tabs(
        [
            tr("Unternehmen", "Company"),
            tr("Position", "Position"),
            tr("Anforderungen", "Requirements"),
            tr("Beschäftigung", "Employment"),
            tr("Vergütung", "Compensation"),
            tr("Prozess", "Process"),
        ]
    )
    with tabs[0]:
        _summary_company()
    with tabs[1]:
        _summary_position()
    with tabs[2]:
        _summary_requirements()
    with tabs[3]:
        _summary_employment()
    with tabs[4]:
        _summary_compensation()
    with tabs[5]:
        _summary_process()

    buff = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    st.download_button(
        "⬇️ Download JSON",
        data=buff,
        file_name="vacalyser_profile.json",
        mime="application/json",
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button(tr("📝 Stellenanzeige (Entwurf)", "📝 Job Ad (Draft)")):
            try:
                job_ad_md = generate_job_ad(data, tone=st.session_state.get("tone"))
                st.session_state[StateKeys.JOB_AD_MD] = job_ad_md
                findings = scan_bias_language(job_ad_md, st.session_state.lang)
                for f in findings:
                    st.warning(
                        tr(
                            f"⚠️ Begriff '{f['term']}' erkannt. Vorschlag: {f['suggestion']}",
                            f"⚠️ Term '{f['term']}' detected. Suggestion: {f['suggestion']}",
                        )
                    )
            except Exception as e:
                st.error(
                    tr(
                        "Job Ad Generierung fehlgeschlagen",
                        "Job ad generation failed",
                    )
                    + f": {e}"
                )
    if st.session_state.get(StateKeys.JOB_AD_MD):
        st.markdown("**Job Ad Draft:**")
        st.markdown(st.session_state[StateKeys.JOB_AD_MD])

    with col_b:
        if st.button(tr("🔎 Boolean String", "🔎 Boolean String")):
            st.session_state[StateKeys.BOOLEAN_STR] = build_boolean_search(data)
    if st.session_state.get(StateKeys.BOOLEAN_STR):
        st.write(tr("**Boolean Search String:**", "**Boolean Search String:**"))
        st.code(st.session_state[StateKeys.BOOLEAN_STR])

    with col_c:
        if st.button(tr("🗂️ Interviewleitfaden", "🗂️ Interview Guide")):
            try:
                profile = NeedAnalysisProfile(**data)
                guide_md = generate_interview_guide(
                    job_title=profile.position.job_title or "",
                    responsibilities="\n".join(profile.responsibilities.items),
                    hard_skills=profile.requirements.hard_skills_required
                    + profile.requirements.hard_skills_optional,
                    soft_skills=profile.requirements.soft_skills_required
                    + profile.requirements.soft_skills_optional,
                    lang=st.session_state.lang,
                    tone=st.session_state.get("tone"),
                    num_questions=5,
                )
                st.session_state[StateKeys.INTERVIEW_GUIDE_MD] = guide_md
            except Exception as e:
                st.error(
                    tr(
                        "Interviewleitfaden Generierung fehlgeschlagen",
                        "Interview guide generation failed",
                    )
                    + f": {e}"
                )
    if st.session_state.get(StateKeys.INTERVIEW_GUIDE_MD):
        st.markdown("**Interview Guide:**")
        st.markdown(st.session_state[StateKeys.INTERVIEW_GUIDE_MD])

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            tr("💡 Follow-ups vorschlagen (LLM)", "💡 Suggest follow-ups (LLM)"),
            type="primary",
        ):
            payload = {"lang": st.session_state.lang, "data": data, "missing": missing}
            try:
                res = ask_followups(
                    payload,
                    model=st.session_state.model,
                    vector_store_id=st.session_state.vector_store_id or None,
                )
                st.session_state["followups"] = res
                st.success(
                    tr("Follow-ups aktualisiert.", "Follow-up questions updated.")
                )
            except Exception as e:
                display_error(
                    tr("Follow-ups fehlgeschlagen", "Follow-ups failed"),
                    str(e),
                )

    with col2:
        if st.session_state.get("followups"):
            st.write(tr("**Vorgeschlagene Fragen:**", "**Suggested questions:**"))
            fu = st.session_state["followups"]
            for item in fu.get("questions", []):
                key = item.get(
                    "key"
                )  # dot key, z.B. "requirements.hard_skills_required"
                q = item.get("question")
                if not key or not q:
                    continue
                st.markdown(f"**{q}**")
                label = tr("Antwort für", "Answer for")
                val = st.text_input(f"{label} {key}", key=f"fu_{key}")
                if val:
                    set_in(data, key, val)

    st.divider()
    if missing:
        st.info(
            tr(
                "Bitte fülle die fehlenden kritischen Felder, um abzuschließen.",
                "Please fill in the remaining critical fields to finish.",
            )
        )
    else:
        st.success(
            tr(
                "Alle kritischen Felder sind befüllt.",
                "All critical fields have been filled.",
            )
        )


# --- Haupt-Wizard-Runner ---
def run_wizard():
    """Run the multi-step vacancy creation wizard.

    Returns:
        None
    """

    # Schema/Config aus app.py Session übernehmen
    schema: dict = st.session_state.get("_schema") or {}
    critical: list[str] = st.session_state.get("_critical_list") or []

    # Falls nicht durch app.py injiziert, lokal nachladen (failsafe)
    if not schema:
        try:
            with (ROOT / "schema" / "need_analysis.schema.json").open(
                "r", encoding="utf-8"
            ) as f:
                schema = json.load(f)
        except Exception:
            schema = {}
    if not critical:
        try:
            with (ROOT / "critical_fields.json").open("r", encoding="utf-8") as f:
                critical = json.load(f).get("critical", [])
        except Exception:
            critical = []

    # Stepbar
    steps = [
        (
            tr(
                "Erstellen Sie eine umfassende Informationssammlung zu Ihrer Vakanz "
                "und nutzen Sie diese Informationen zur Optimierung aller folgenden "
                "Schritte Ihres Recruitment-Prozesses",
                "Create a comprehensive information collection for your vacancy and "
                "use this information to optimize all subsequent steps of your "
                "recruitment process",
            ),
            _step_intro,
        ),
        (tr("Quelle", "Source"), lambda: _step_source(schema)),
        (tr("Unternehmen", "Company"), _step_company),
        (tr("Position", "Position"), _step_position),
        (tr("Anforderungen", "Requirements"), _step_requirements),
        (tr("Beschäftigung", "Employment"), _step_employment),
        (tr("Vergütung", "Compensation"), _step_compensation),
        (tr("Prozess", "Process"), _step_process),
        (tr("Summary", "Summary"), lambda: _step_summary(schema, critical)),
    ]

    # Headline
    st.markdown("### 🧭 Wizard")

    # Step Navigation (oben)
    render_stepper(st.session_state[StateKeys.STEP], len(steps))
    st.caption(
        tr(
            "Klicke auf 'Weiter' oder navigiere direkt zu einem Schritt.",
            "Click 'Next' or navigate directly to a step.",
        )
    )

    # Render current step
    current = st.session_state[StateKeys.STEP]
    label, renderer = steps[current]
    step_word = tr("Schritt", "Step")
    st.markdown(f"#### {step_word} {current + 1} — {label}")
    renderer()

    # Bottom nav
    crit_until_now = [f for f in critical if FIELD_SECTION_MAP.get(f, 0) <= current + 1]
    missing = missing_keys(st.session_state[StateKeys.PROFILE], crit_until_now)

    if missing:
        st.warning(f"{t('missing', st.session_state.lang)} {', '.join(missing)}")

    if current == 0:
        _, col_next, _ = st.columns([1, 1, 1])
        with col_next:
            if current < len(steps) - 1 and st.button(
                tr("Weiter ▶︎", "Next ▶︎"),
                type="primary",
                use_container_width=True,
            ):
                next_step()
                st.rerun()
    elif current == 1:
        col_prev, col_skip, col_next = st.columns([1, 1, 1])
        with col_prev:
            if st.button(tr("◀︎ Zurück", "◀︎ Back"), use_container_width=True):
                prev_step()
                st.rerun()
        with col_skip:
            if st.button(tr("Überspringen", "Skip"), use_container_width=True):
                next_step()
                st.rerun()
        with col_next:
            if st.button(
                tr("Weiter ▶︎", "Next ▶︎"),
                type="primary",
                use_container_width=True,
            ):
                next_step()
                st.rerun()
    else:
        col_prev, col_next = st.columns([1, 1])
        with col_prev:
            if st.button(tr("◀︎ Zurück", "◀︎ Back"), use_container_width=True):
                prev_step()
                st.rerun()
        with col_next:
            if current < len(steps) - 1:
                if st.button(
                    tr("Weiter ▶︎", "Next ▶︎"),
                    type="primary",
                    use_container_width=True,
                ):
                    next_step()
                    st.rerun()
            else:
                if st.button(
                    tr("Fertig", "Done"), type="primary", use_container_width=True
                ):
                    st.session_state[StateKeys.STEP] = 0
                    st.rerun()
