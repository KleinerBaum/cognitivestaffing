# wizard.py — Vacalyser Wizard (clean flow, schema-aligned)
from __future__ import annotations

import io
import json
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
from openai_utils import extract_with_function  # nutzt deine neue Definition
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from integrations.esco import search_occupation, enrich_skills
from components.stepper import render_stepper

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
            tr("Datei konnte nicht gelesen werden", "Failed to read file"),
            str(e),
        )
        return
    if not txt.strip():
        display_error(
            tr("Datei enthält keinen Text", "File contains no text"),
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
        display_error(tr("Ungültige URL", "Invalid URL"))
        return
    try:
        txt = extract_text_from_url(url)
    except Exception as e:  # pragma: no cover - defensive
        display_error(
            tr("URL konnte nicht geladen werden", "Failed to fetch URL"),
            str(e),
        )
        return
    if not txt or not txt.strip():
        display_error(
            tr("Keine Textinhalte gefunden", "No text content found"),
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
    "requirements.hard_skills": 3,
    "requirements.soft_skills": 3,
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

    st.title(t("intro_title", st.session_state.lang))
    st.write(
        tr(
            "Dieser Assistent führt dich in wenigen Schritten zu einem vollständigen, strukturierten Stellenprofil.",
            "This assistant guides you in a few steps to a complete, structured job profile.",
        )
    )
    with st.expander("Vorteile / Advantages"):
        st.markdown(
            """
- Schnellere, vollständigere Anforderungsaufnahme
- ESCO-gestützte Skill-Vervollständigung
- Strukturierte Daten → bessere Suche & Matching
- Klarere Ausschreibungen → bessere Candidate Experience
"""
        )


def _step_source(schema: dict) -> None:
    """Render the source step where users choose text, file, or URL."""

    st.subheader(t("source", st.session_state.lang))
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
        )

    with tab_file:
        st.file_uploader(
            tr("JD hochladen (PDF/DOCX/TXT)", "Upload JD (PDF/DOCX/TXT)"),
            type=["pdf", "docx", "txt"],
            key=UIKeys.JD_FILE_UPLOADER,
            on_change=on_file_uploaded,
        )

    with tab_url:
        st.text_input(
            tr("oder eine Job-URL eingeben", "or enter a Job URL"),
            key=UIKeys.JD_URL_INPUT,
            on_change=on_url_changed,
        )

    text_for_extract = st.session_state.get(StateKeys.RAW_TEXT, "").strip()
    if st.button(t("analyze", st.session_state.lang), type="primary"):
        if not text_for_extract:
            st.warning(
                tr(
                    "Bitte zuerst eine Quelle angeben.",
                    "Please provide a source first.",
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
                    current_skills = set(profile.requirements.hard_skills or [])
                    merged = sorted(current_skills.union(skills or []))
                    profile.requirements.hard_skills = merged
                st.session_state[StateKeys.PROFILE] = profile.model_dump()
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
                st.session_state[StateKeys.STEP] = 2
                st.rerun()
            except Exception as e:
                display_error(
                    tr("Extraktion fehlgeschlagen", "Extraction failed"),
                    str(e),
                )


def _step_company():
    """Render the company information step.

    Returns:
        None
    """

    st.subheader(tr("Unternehmen", "Company"))
    data = st.session_state[StateKeys.PROFILE]

    c1, c2 = st.columns(2)
    data["company"]["name"] = c1.text_input(
        tr("Firma *", "Company *"), value=data["company"].get("name", "")
    )
    data["company"]["industry"] = c2.text_input(
        tr("Branche", "Industry"), value=data["company"].get("industry", "")
    )

    c3, c4 = st.columns(2)
    data["company"]["hq_location"] = c3.text_input(
        tr("Hauptsitz", "Headquarters"),
        value=data["company"].get("hq_location", ""),
    )
    data["company"]["size"] = c4.text_input(
        tr("Größe", "Size"), value=data["company"].get("size", "")
    )

    c5, c6 = st.columns(2)
    data["company"]["website"] = c5.text_input(
        tr("Website", "Website"), value=data["company"].get("website", "")
    )
    data["company"]["mission"] = c6.text_input(
        tr("Mission", "Mission"), value=data["company"].get("mission", "")
    )

    data["company"]["culture"] = st.text_area(
        tr("Kultur", "Culture"), value=data["company"].get("culture", "")
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


def _step_position():
    """Render the position details step.

    Returns:
        None
    """

    st.subheader(tr("Position", "Position"))
    data = st.session_state[StateKeys.PROFILE]

    c1, c2 = st.columns(2)
    data["position"]["job_title"] = c1.text_input(
        tr("Jobtitel *", "Job title *"), value=data["position"].get("job_title", "")
    )
    data["position"]["seniority_level"] = c2.text_input(
        tr("Seniorität", "Seniority"), value=data["position"].get("seniority_level", "")
    )

    c3, c4 = st.columns(2)
    data["position"]["department"] = c3.text_input(
        tr("Abteilung", "Department"), value=data["position"].get("department", "")
    )
    data["position"]["team_structure"] = c4.text_input(
        tr("Teamstruktur", "Team structure"),
        value=data["position"].get("team_structure", ""),
    )

    c5, c6 = st.columns(2)
    data["position"]["reporting_line"] = c5.text_input(
        tr("Reports an", "Reports to"), value=data["position"].get("reporting_line", "")
    )
    data["position"]["role_summary"] = c6.text_area(
        tr("Rollen-Summary *", "Role summary *"),
        value=data["position"].get("role_summary", ""),
        height=120,
    )

    # Inline follow-up questions for Position and Location section
    if StateKeys.FOLLOWUPS in st.session_state:
        for q in list(st.session_state[StateKeys.FOLLOWUPS]):
            field = q.get("field", "")
            if field.startswith("position.") or field.startswith("location."):
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
    data = st.session_state[StateKeys.PROFILE]

    data["requirements"]["hard_skills"] = _chip_multiselect(
        "Hard Skills",
        options=data["requirements"].get("hard_skills", []),
        values=data["requirements"].get("hard_skills", []),
    )
    data["requirements"]["soft_skills"] = _chip_multiselect(
        "Soft Skills",
        options=data["requirements"].get("soft_skills", []),
        values=data["requirements"].get("soft_skills", []),
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
    data["requirements"]["certifications"] = _chip_multiselect(
        tr("Zertifizierungen", "Certifications"),
        options=data["requirements"].get("certifications", []),
        values=data["requirements"].get("certifications", []),
    )

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

    c3, c4, c5 = st.columns(3)
    data["employment"]["travel_required"] = c3.toggle(
        tr("Reisetätigkeit?", "Travel required?"),
        value=bool(data["employment"].get("travel_required")),
    )
    data["employment"]["relocation_support"] = c4.toggle(
        tr("Relocation?", "Relocation?"),
        value=bool(data["employment"].get("relocation_support")),
    )
    data["employment"]["visa_sponsorship"] = c5.toggle(
        tr("Visum-Sponsoring?", "Visa sponsorship?"),
        value=bool(data["employment"].get("visa_sponsorship")),
    )

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
    data = st.session_state[StateKeys.PROFILE]

    c1, c2, c3 = st.columns(3)
    data["compensation"]["salary_min"] = c1.number_input(
        tr("Gehalt min", "Salary min"),
        value=float(data["compensation"].get("salary_min") or 0.0),
    )
    data["compensation"]["salary_max"] = c2.number_input(
        tr("Gehalt max", "Salary max"),
        value=float(data["compensation"].get("salary_max") or 0.0),
    )
    data["compensation"]["currency"] = c3.text_input(
        tr("Währung", "Currency"), value=data["compensation"].get("currency", "")
    )

    c4, c5 = st.columns(2)
    period_options = ["year", "month", "day", "hour"]
    current_period = data["compensation"].get("period")
    data["compensation"]["period"] = c4.selectbox(
        tr("Periode", "Period"),
        options=period_options,
        index=(
            period_options.index(current_period)
            if current_period in period_options
            else 0
        ),
    )
    data["compensation"]["variable_pay"] = c5.toggle(
        tr("Variable Vergütung?", "Variable pay?"),
        value=bool(data["compensation"].get("variable_pay")),
    )

    c6, c7 = st.columns(2)
    data["compensation"]["equity_offered"] = c6.toggle(
        "Equity?", value=bool(data["compensation"].get("equity_offered"))
    )
    data["compensation"]["benefits"] = _chip_multiselect(
        "Benefits",
        options=data["compensation"].get("benefits", []),
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
    """Render the hiring process step.

    Returns:
        None
    """

    st.subheader(tr("Prozess", "Process"))
    data = st.session_state[StateKeys.PROFILE]

    c1, c2 = st.columns([1, 2])
    init_val = data["process"].get("interview_stages")
    data["process"]["interview_stages"] = int(
        c1.number_input(
            tr("Phasen", "Stages"),
            value=int(init_val) if init_val is not None else 0,
        )
    )
    data["process"]["process_notes"] = c2.text_area(
        tr("Notizen", "Notes"), value=data["process"].get("process_notes", "")
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
                    set_in(data, field, ans)
                    st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _step_summary(schema: dict, critical: list[str]):
    """Render the summary step and offer follow-up questions.

    Args:
        schema: Schema defining allowed fields.
        critical: Keys that must be present in ``data``.

    Returns:
        None
    """

    st.subheader(tr("Zusammenfassung", "Summary"))
    data = st.session_state[StateKeys.PROFILE]
    missing = missing_keys(data, critical)
    if missing:
        st.warning(f"{t('missing', st.session_state.lang)} {', '.join(missing)}")

    st.json(data)

    buff = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    st.download_button(
        "⬇️ Download JSON",
        data=buff,
        file_name="vacalyser_profile.json",
        mime="application/json",
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button(
            tr("📝 Stellenanzeige (Entwurf)", "📝 Job Ad (Draft)"),
        ):
            st.info(tr("Noch nicht implementiert.", "Not implemented yet."))
    with col_b:
        if st.button(
            tr("🔎 Boolean String", "🔎 Boolean String"),
        ):
            st.info(tr("Noch nicht implementiert.", "Not implemented yet."))
    with col_c:
        if st.button(
            tr("🗂️ Interviewleitfaden", "🗂️ Interview Guide"),
        ):
            st.info(tr("Noch nicht implementiert.", "Not implemented yet."))

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
                key = item.get("key")  # dot key, z.B. "requirements.hard_skills"
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
        (tr("Intro", "Intro"), _step_intro),
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
    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if current > 0 and st.button(
            tr("◀︎ Zurück", "◀︎ Back"), use_container_width=True
        ):
            prev_step()
            st.rerun()
    with col_next:
        if current < len(steps) - 1:
            if st.button(
                tr("Weiter ▶︎", "Next ▶︎"), type="primary", use_container_width=True
            ):
                crit_until_now = [
                    f for f in critical if FIELD_SECTION_MAP.get(f, 0) <= current + 1
                ]
                missing = missing_keys(
                    st.session_state[StateKeys.PROFILE], crit_until_now
                )
                if missing:
                    st.warning(
                        f"{t('missing', st.session_state.lang)} {', '.join(missing)}"
                    )
                else:
                    next_step()
                    st.rerun()
        else:
            st.button(
                tr("Fertig", "Done"),
                disabled=bool(
                    missing_keys(st.session_state[StateKeys.PROFILE], critical)
                ),
            )
