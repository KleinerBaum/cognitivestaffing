# wizard.py — Vacalyser Wizard (clean flow, schema-aligned)
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import List

import streamlit as st

from utils.i18n import tr
from i18n import t

# LLM/ESCO und Follow-ups
from openai_utils import extract_with_function  # nutzt deine neue Definition
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from core.esco_utils import classify_occupation, get_essential_skills

ROOT = Path(__file__).parent

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
def get_in(d: dict, path: str, default=None):
    """Retrieve a nested value from a dict using dot notation.

    Args:
        d: Dictionary to traverse.
        path: Dot-separated key path.
        default: Value returned if the path is missing.

    Returns:
        The value at the given path or ``default`` if not found.
    """

    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def set_in(d: dict, path: str, value):
    """Assign a value in a nested dict via dot-separated path.

    Args:
        d: Dictionary to modify.
        path: Dot-separated key path.
        value: Value to set at the path.

    Returns:
        None
    """

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


def ensure_path(d: dict, path: str):
    """Ensure that a nested path exists in a dict.

    Missing segments are created with ``None`` values.

    Args:
        d: Dictionary to update.
        path: Dot-separated key path.

    Returns:
        None
    """

    set_in(d, path, get_in(d, path, None))


def flatten(d: dict, prefix: str = ""):
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


def _step_source(schema: dict):
    """Render the source step where users choose text, file, or URL."""

    st.subheader(t("source", st.session_state.lang))
    tab_text, tab_file, tab_url = st.tabs(
        [tr("Text", "Text"), tr("Datei", "File"), tr("URL", "URL")]
    )

    with tab_text:
        jd_text = st.text_area(tr("Jobtext", "Job text"), height=220, key="jd_text")

    with tab_file:
        up = st.file_uploader(
            tr("PDF/DOCX auswählen", "Select PDF/DOCX"),
            type=["pdf", "docx"],
            key="jd_upload",
        )
        if up and st.button(tr("Datei analysieren", "Analyze file")):
            from utils.pdf_utils import extract_text_from_file

            st.session_state.jd_text = extract_text_from_file(up)
            st.success(
                tr(
                    "Datei gelesen. Text im Text-Tab bearbeitbar.",
                    "File processed. Text available in Text tab.",
                )
            )

    with tab_url:
        url = st.text_input(tr("URL zu Jobanzeige", "Job ad URL"), key="jd_url")
        if url and st.button(tr("URL analysieren", "Analyze URL")):
            from utils.url_utils import extract_text_from_url

            st.session_state.jd_text = extract_text_from_url(url)
            st.success(
                tr(
                    "URL gelesen. Text im Text-Tab bearbeitbar.",
                    "URL processed. Text available in Text tab.",
                )
            )

    text_for_extract = st.session_state.get("jd_text") or jd_text
    if st.button(t("analyze", st.session_state.lang), type="primary"):
        if not (text_for_extract or "").strip():
            st.warning(
                tr(
                    "Bitte zuerst eine Quelle angeben.",
                    "Please provide a source first.",
                )
            )
        else:
            try:
                data = extract_with_function(
                    text_for_extract, schema, model=st.session_state.model
                )
                st.session_state.data = data
                title = get_in(st.session_state.data, "position.job_title", "")
                occ = (
                    classify_occupation(title, st.session_state.lang or "en")
                    if title
                    else None
                )
                if occ:
                    set_in(
                        st.session_state.data,
                        "position.occupation_label",
                        occ.get("preferredLabel"),
                    )
                    set_in(
                        st.session_state.data,
                        "position.occupation_uri",
                        occ.get("uri"),
                    )
                    set_in(
                        st.session_state.data,
                        "position.occupation_group",
                        occ.get("group"),
                    )
                    skills = get_essential_skills(
                        occ.get("uri"), st.session_state.lang or "en"
                    )
                    current = set(
                        get_in(st.session_state.data, "requirements.hard_skills", [])
                        or []
                    )
                    merged = sorted(current.union(set(skills)))
                    set_in(st.session_state.data, "requirements.hard_skills", merged)
                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                st.error(f"{tr('Extraktion fehlgeschlagen', 'Extraction failed')}: {e}")


def _step_company():
    """Render the company information step.

    Returns:
        None
    """

    st.subheader(tr("Unternehmen", "Company"))
    data = st.session_state.data
    ensure_path(data, "company.name")
    ensure_path(data, "company.industry")
    ensure_path(data, "company.hq_location")
    ensure_path(data, "company.size")
    ensure_path(data, "company.website")
    ensure_path(data, "company.mission")
    ensure_path(data, "company.culture")

    c1, c2 = st.columns(2)
    set_in(
        data,
        "company.name",
        c1.text_input(
            tr("Firma *", "Company *"), value=get_in(data, "company.name", "")
        ),
    )
    set_in(
        data,
        "company.industry",
        c2.text_input(
            tr("Branche", "Industry"), value=get_in(data, "company.industry", "")
        ),
    )

    c3, c4 = st.columns(2)
    set_in(
        data,
        "company.hq_location",
        c3.text_input(
            tr("Hauptsitz", "Headquarters"),
            value=get_in(data, "company.hq_location", ""),
        ),
    )
    set_in(
        data,
        "company.size",
        c4.text_input(tr("Größe", "Size"), value=get_in(data, "company.size", "")),
    )

    c5, c6 = st.columns(2)
    set_in(
        data,
        "company.website",
        c5.text_input(
            tr("Website", "Website"), value=get_in(data, "company.website", "")
        ),
    )
    set_in(
        data,
        "company.mission",
        c6.text_input(
            tr("Mission", "Mission"), value=get_in(data, "company.mission", "")
        ),
    )

    set_in(
        data,
        "company.culture",
        st.text_area(
            tr("Kultur", "Culture"), value=get_in(data, "company.culture", "")
        ),
    )


def _step_position():
    """Render the position details step.

    Returns:
        None
    """

    st.subheader(tr("Position", "Position"))
    data = st.session_state.data
    ensure_path(data, "position.job_title")
    ensure_path(data, "position.seniority_level")
    ensure_path(data, "position.department")
    ensure_path(data, "position.team_structure")
    ensure_path(data, "position.reporting_line")
    ensure_path(data, "position.role_summary")

    c1, c2 = st.columns(2)
    set_in(
        data,
        "position.job_title",
        c1.text_input(
            tr("Jobtitel *", "Job title *"),
            value=get_in(data, "position.job_title", ""),
        ),
    )
    set_in(
        data,
        "position.seniority_level",
        c2.text_input(
            tr("Seniorität", "Seniority"),
            value=get_in(data, "position.seniority_level", ""),
        ),
    )

    c3, c4 = st.columns(2)
    set_in(
        data,
        "position.department",
        c3.text_input(
            tr("Abteilung", "Department"), value=get_in(data, "position.department", "")
        ),
    )
    set_in(
        data,
        "position.team_structure",
        c4.text_input(
            tr("Teamstruktur", "Team structure"),
            value=get_in(data, "position.team_structure", ""),
        ),
    )

    c5, c6 = st.columns(2)
    set_in(
        data,
        "position.reporting_line",
        c5.text_input(
            tr("Reports an", "Reports to"),
            value=get_in(data, "position.reporting_line", ""),
        ),
    )
    set_in(
        data,
        "position.role_summary",
        c6.text_area(
            tr("Rollen-Summary *", "Role summary *"),
            value=get_in(data, "position.role_summary", ""),
            height=120,
        ),
    )


def _step_requirements():
    """Render the requirements step for skills and certifications.

    Returns:
        None
    """

    st.subheader(tr("Anforderungen", "Requirements"))
    data = st.session_state.data
    ensure_path(data, "requirements.hard_skills")
    ensure_path(data, "requirements.soft_skills")
    ensure_path(data, "requirements.tools_and_technologies")
    ensure_path(data, "requirements.languages_required")
    ensure_path(data, "requirements.certifications")

    set_in(
        data,
        "requirements.hard_skills",
        _chip_multiselect(
            "Hard Skills",
            options=get_in(data, "requirements.hard_skills", []) or [],
            values=get_in(data, "requirements.hard_skills", []) or [],
        ),
    )
    set_in(
        data,
        "requirements.soft_skills",
        _chip_multiselect(
            "Soft Skills",
            options=get_in(data, "requirements.soft_skills", []) or [],
            values=get_in(data, "requirements.soft_skills", []) or [],
        ),
    )
    set_in(
        data,
        "requirements.tools_and_technologies",
        _chip_multiselect(
            "Tools & Tech",
            options=get_in(data, "requirements.tools_and_technologies", []) or [],
            values=get_in(data, "requirements.tools_and_technologies", []) or [],
        ),
    )
    set_in(
        data,
        "requirements.languages_required",
        _chip_multiselect(
            tr("Sprachen", "Languages"),
            options=get_in(data, "requirements.languages_required", []) or [],
            values=get_in(data, "requirements.languages_required", []) or [],
        ),
    )
    set_in(
        data,
        "requirements.certifications",
        _chip_multiselect(
            tr("Zertifizierungen", "Certifications"),
            options=get_in(data, "requirements.certifications", []) or [],
            values=get_in(data, "requirements.certifications", []) or [],
        ),
    )


def _step_employment():
    """Render the employment details step.

    Returns:
        None
    """

    st.subheader(tr("Beschäftigung", "Employment"))
    data = st.session_state.data
    ensure_path(data, "employment.job_type")
    ensure_path(data, "employment.work_policy")
    ensure_path(data, "employment.travel_required")
    ensure_path(data, "employment.relocation_support")
    ensure_path(data, "employment.visa_sponsorship")

    c1, c2 = st.columns(2)
    set_in(
        data,
        "employment.job_type",
        c1.selectbox(
            tr("Art", "Type"),
            options=[
                "full_time",
                "part_time",
                "contract",
                "internship",
                "temporary",
                "other",
            ],
            index=(
                0
                if not get_in(data, "employment.job_type")
                else [
                    "full_time",
                    "part_time",
                    "contract",
                    "internship",
                    "temporary",
                    "other",
                ].index(get_in(data, "employment.job_type"))
            ),
        ),
    )
    set_in(
        data,
        "employment.work_policy",
        c2.selectbox(
            tr("Policy", "Policy"),
            options=["onsite", "hybrid", "remote"],
            index=(
                0
                if not get_in(data, "employment.work_policy")
                else ["onsite", "hybrid", "remote"].index(
                    get_in(data, "employment.work_policy")
                )
            ),
        ),
    )

    c3, c4, c5 = st.columns(3)
    set_in(
        data,
        "employment.travel_required",
        c3.toggle(
            tr("Reisetätigkeit?", "Travel required?"),
            value=bool(get_in(data, "employment.travel_required", False)),
        ),
    )
    set_in(
        data,
        "employment.relocation_support",
        c4.toggle(
            tr("Relocation?", "Relocation?"),
            value=bool(get_in(data, "employment.relocation_support", False)),
        ),
    )
    set_in(
        data,
        "employment.visa_sponsorship",
        c5.toggle(
            tr("Visum-Sponsoring?", "Visa sponsorship?"),
            value=bool(get_in(data, "employment.visa_sponsorship", False)),
        ),
    )


def _step_compensation():
    """Render the compensation and benefits step.

    Returns:
        None
    """

    st.subheader(tr("Vergütung & Benefits", "Compensation & Benefits"))
    data = st.session_state.data
    ensure_path(data, "compensation.salary_min")
    ensure_path(data, "compensation.salary_max")
    ensure_path(data, "compensation.currency")
    ensure_path(data, "compensation.period")
    ensure_path(data, "compensation.variable_pay")
    ensure_path(data, "compensation.equity_offered")
    ensure_path(data, "compensation.benefits")

    c1, c2, c3 = st.columns(3)
    set_in(
        data,
        "compensation.salary_min",
        c1.number_input(
            tr("Gehalt min", "Salary min"),
            value=(
                float(get_in(data, "compensation.salary_min", 0))
                if get_in(data, "compensation.salary_min") is not None
                else 0.0
            ),
        ),
    )
    set_in(
        data,
        "compensation.salary_max",
        c2.number_input(
            tr("Gehalt max", "Salary max"),
            value=(
                float(get_in(data, "compensation.salary_max", 0))
                if get_in(data, "compensation.salary_max") is not None
                else 0.0
            ),
        ),
    )
    set_in(
        data,
        "compensation.currency",
        c3.text_input(
            tr("Währung", "Currency"), value=get_in(data, "compensation.currency", "")
        ),
    )

    c4, c5 = st.columns(2)
    set_in(
        data,
        "compensation.period",
        c4.selectbox(
            tr("Periode", "Period"),
            options=["year", "month", "day", "hour"],
            index=(
                0
                if not get_in(data, "compensation.period")
                else ["year", "month", "day", "hour"].index(
                    get_in(data, "compensation.period")
                )
            ),
        ),
    )
    set_in(
        data,
        "compensation.variable_pay",
        c5.toggle(
            tr("Variable Vergütung?", "Variable pay?"),
            value=bool(get_in(data, "compensation.variable_pay", False)),
        ),
    )

    c6, c7 = st.columns(2)
    set_in(
        data,
        "compensation.equity_offered",
        c6.toggle(
            "Equity?", value=bool(get_in(data, "compensation.equity_offered", False))
        ),
    )
    set_in(
        data,
        "compensation.benefits",
        _chip_multiselect(
            "Benefits",
            options=get_in(data, "compensation.benefits", []) or [],
            values=get_in(data, "compensation.benefits", []) or [],
        ),
    )


def _step_process():
    """Render the hiring process step.

    Returns:
        None
    """

    st.subheader(tr("Prozess", "Process"))
    data = st.session_state.data
    ensure_path(data, "process.interview_stages")
    ensure_path(data, "process.process_notes")

    c1, c2 = st.columns([1, 2])
    init_val = get_in(data, "process.interview_stages")
    set_in(
        data,
        "process.interview_stages",
        int(
            c1.number_input(
                tr("Phasen", "Stages"),
                value=int(init_val) if init_val is not None else 0,
            )
        ),
    )
    set_in(
        data,
        "process.process_notes",
        c2.text_area(
            tr("Notizen", "Notes"), value=get_in(data, "process.process_notes", "")
        ),
    )


def _step_summary(schema: dict, critical: list[str]):
    """Render the summary step and offer follow-up questions.

    Args:
        schema: Schema defining allowed fields.
        critical: Keys that must be present in ``data``.

    Returns:
        None
    """

    st.subheader(tr("Zusammenfassung", "Summary"))
    data = st.session_state.data
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
                st.error(f"{tr('Follow-ups fehlgeschlagen', 'Follow-ups failed')}: {e}")

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
            with (ROOT / "vacalyser_schema.json").open("r", encoding="utf-8") as f:
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
    st.progress((st.session_state.step + 1) / len(steps))
    st.caption(
        tr(
            "Klicke auf 'Weiter' oder navigiere direkt zu einem Schritt.",
            "Click 'Next' or navigate directly to a step.",
        )
    )

    # Render current step
    label, renderer = steps[st.session_state.step]
    step_word = tr("Schritt", "Step")
    st.markdown(f"#### {step_word} {st.session_state.step + 1} — {label}")
    renderer()

    # Bottom nav
    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if st.session_state.step > 0 and st.button(
            tr("◀︎ Zurück", "◀︎ Back"), use_container_width=True
        ):
            st.session_state.step -= 1
            st.rerun()
    with col_next:
        # Gating: auf Summary erst, ansonsten immer weiter
        if st.session_state.step < len(steps) - 1:
            if st.button(
                tr("Weiter ▶︎", "Next ▶︎"), type="primary", use_container_width=True
            ):
                st.session_state.step += 1
                st.rerun()
        else:
            st.button(
                tr("Fertig", "Done"),
                disabled=bool(missing_keys(st.session_state.data, critical)),
            )
