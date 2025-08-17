# wizard.py — Vacalyser Wizard (clean flow, schema-aligned)
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import streamlit as st

# LLM/ESCO und Follow-ups
from openai_utils import extract_with_function  # nutzt deine neue Definition
from question_logic import ask_followups  # nutzt deine neue Definition
from core.esco_utils import classify_occupation, get_essential_skills

ROOT = Path(__file__).parent


# --- Hilfsfunktionen: Dot-Notation lesen/schreiben ---
def get_in(d: dict, path: str, default=None):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def set_in(d: dict, path: str, value):
    cur = d
    parts = path.split(".")
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def ensure_path(d: dict, path: str):
    set_in(d, path, get_in(d, path, None))


def flatten(d: dict, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def missing_keys(data: dict, critical: List[str]) -> List[str]:
    flat = flatten(data)
    return [k for k in critical if (k not in flat) or (flat[k] in (None, "", [], {}))]


# --- UI-Komponenten ---
def _chip_multiselect(label: str, options: List[str], values: List[str]) -> List[str]:
    # Einfache, robuste Multiselect-Variante
    return st.multiselect(label, options=options, default=values, key=f"ms_{label}")


# --- Step-Renderers ---
def _step_intro():
    st.title("Vacalyser — Wizard")
    st.write("Dieser Assistent führt dich in wenigen Schritten zu einem vollständigen, strukturierten Stellenprofil.")


def _step_source(schema: dict):
    st.subheader("Quelle / Anreicherung")
    jd_text = st.text_area("Jobtext (einfügen oder kurz beschreiben)", height=220, key="jd_text")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔎 Automatisch analysieren (LLM)", type="primary"):
            if not jd_text.strip():
                st.warning("Bitte zuerst einen Jobtext einfügen.")
            else:
                try:
                    data = extract_with_function(jd_text, schema, model=st.session_state.model)
                    st.session_state.data = data  # HARTE Zuweisung: Schema-konform
                    st.success("Extraktion abgeschlossen.")
                    # ESCO-Klassifikation optional nachziehen
                    title = get_in(st.session_state.data, "position.job_title", "")
                    occ = classify_occupation(title, st.session_state.lang or "en") if title else None
                    if occ:
                        set_in(st.session_state.data, "position.occupation_label", occ.get("label"))
                        set_in(st.session_state.data, "position.occupation_uri", occ.get("uri"))
                        set_in(st.session_state.data, "position.occupation_group", occ.get("group"))
                        skills = get_essential_skills(occ.get("uri"), st.session_state.lang or "en")
                        # Merge in requirements.hard_skills ohne Duplikate
                        current = set(get_in(st.session_state.data, "requirements.hard_skills", []) or [])
                        merged = sorted(current.union(skills))
                        set_in(st.session_state.data, "requirements.hard_skills", merged)
                    st.session_state.step = 2  # springe direkt zu Firma
                    st.rerun()
                except Exception as e:
                    st.error(f"Extraktion fehlgeschlagen: {e}")
    with col2:
        st.info(
            "Optional: RAG via Vector Store wird bei Follow-ups berücksichtigt, wenn `VECTOR_STORE_ID` gesetzt ist.",
            icon="ℹ️",
        )


def _step_company():
    st.subheader("Unternehmen")
    data = st.session_state.data
    ensure_path(data, "company.name")
    ensure_path(data, "company.industry")
    ensure_path(data, "company.hq_location")
    ensure_path(data, "company.size")
    ensure_path(data, "company.website")
    ensure_path(data, "company.mission")
    ensure_path(data, "company.culture")

    c1, c2 = st.columns(2)
    set_in(data, "company.name", c1.text_input("Firma *", value=get_in(data, "company.name", "")))
    set_in(data, "company.industry", c2.text_input("Branche", value=get_in(data, "company.industry", "")))

    c3, c4 = st.columns(2)
    set_in(data, "company.hq_location", c3.text_input("Hauptsitz", value=get_in(data, "company.hq_location", "")))
    set_in(data, "company.size", c4.text_input("Größe", value=get_in(data, "company.size", "")))

    c5, c6 = st.columns(2)
    set_in(data, "company.website", c5.text_input("Website", value=get_in(data, "company.website", "")))
    set_in(data, "company.mission", c6.text_input("Mission", value=get_in(data, "company.mission", "")))

    set_in(data, "company.culture", st.text_area("Kultur", value=get_in(data, "company.culture", "")))


def _step_position():
    st.subheader("Position")
    data = st.session_state.data
    ensure_path(data, "position.job_title")
    ensure_path(data, "position.seniority_level")
    ensure_path(data, "position.department")
    ensure_path(data, "position.team_structure")
    ensure_path(data, "position.reporting_line")
    ensure_path(data, "position.role_summary")

    c1, c2 = st.columns(2)
    set_in(data, "position.job_title", c1.text_input("Jobtitel *", value=get_in(data, "position.job_title", "")))
    set_in(
        data,
        "position.seniority_level",
        c2.text_input("Seniorität", value=get_in(data, "position.seniority_level", "")),
    )

    c3, c4 = st.columns(2)
    set_in(data, "position.department", c3.text_input("Abteilung", value=get_in(data, "position.department", "")))
    set_in(
        data,
        "position.team_structure",
        c4.text_input("Teamstruktur", value=get_in(data, "position.team_structure", "")),
    )

    c5, c6 = st.columns(2)
    set_in(
        data, "position.reporting_line", c5.text_input("Reports an", value=get_in(data, "position.reporting_line", ""))
    )
    set_in(
        data,
        "position.role_summary",
        c6.text_area("Rollen-Summary *", value=get_in(data, "position.role_summary", ""), height=120),
    )


def _step_requirements():
    st.subheader("Anforderungen")
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
            "Sprachen",
            options=get_in(data, "requirements.languages_required", []) or [],
            values=get_in(data, "requirements.languages_required", []) or [],
        ),
    )
    set_in(
        data,
        "requirements.certifications",
        _chip_multiselect(
            "Zertifizierungen",
            options=get_in(data, "requirements.certifications", []) or [],
            values=get_in(data, "requirements.certifications", []) or [],
        ),
    )


def _step_employment():
    st.subheader("Beschäftigung")
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
            "Art",
            options=["full_time", "part_time", "contract", "internship", "temporary", "other"],
            index=(
                0
                if not get_in(data, "employment.job_type")
                else ["full_time", "part_time", "contract", "internship", "temporary", "other"].index(
                    get_in(data, "employment.job_type")
                )
            ),
        ),
    )
    set_in(
        data,
        "employment.work_policy",
        c2.selectbox(
            "Policy",
            options=["onsite", "hybrid", "remote"],
            index=(
                0
                if not get_in(data, "employment.work_policy")
                else ["onsite", "hybrid", "remote"].index(get_in(data, "employment.work_policy"))
            ),
        ),
    )

    c3, c4, c5 = st.columns(3)
    set_in(
        data,
        "employment.travel_required",
        c3.toggle("Reisetätigkeit?", value=bool(get_in(data, "employment.travel_required", False))),
    )
    set_in(
        data,
        "employment.relocation_support",
        c4.toggle("Relocation?", value=bool(get_in(data, "employment.relocation_support", False))),
    )
    set_in(
        data,
        "employment.visa_sponsorship",
        c5.toggle("Visum-Sponsoring?", value=bool(get_in(data, "employment.visa_sponsorship", False))),
    )


def _step_compensation():
    st.subheader("Vergütung & Benefits")
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
            "Gehalt min",
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
            "Gehalt max",
            value=(
                float(get_in(data, "compensation.salary_max", 0))
                if get_in(data, "compensation.salary_max") is not None
                else 0.0
            ),
        ),
    )
    set_in(data, "compensation.currency", c3.text_input("Währung", value=get_in(data, "compensation.currency", "")))

    c4, c5 = st.columns(2)
    set_in(
        data,
        "compensation.period",
        c4.selectbox(
            "Periode",
            options=["year", "month", "day", "hour"],
            index=(
                0
                if not get_in(data, "compensation.period")
                else ["year", "month", "day", "hour"].index(get_in(data, "compensation.period"))
            ),
        ),
    )
    set_in(
        data,
        "compensation.variable_pay",
        c5.toggle("Variable Vergütung?", value=bool(get_in(data, "compensation.variable_pay", False))),
    )

    c6, c7 = st.columns(2)
    set_in(
        data,
        "compensation.equity_offered",
        c6.toggle("Equity?", value=bool(get_in(data, "compensation.equity_offered", False))),
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
    st.subheader("Prozess")
    data = st.session_state.data
    ensure_path(data, "process.interview_stages")
    ensure_path(data, "process.process_notes")

    c1, c2 = st.columns([1, 2])
    init_val = get_in(data, "process.interview_stages")
    set_in(
        data,
        "process.interview_stages",
        int(c1.number_input("Stages", value=int(init_val) if init_val is not None else 0)),
    )
    set_in(data, "process.process_notes", c2.text_area("Notizen", value=get_in(data, "process.process_notes", "")))


def _step_summary(schema: dict, critical: list[str]):
    st.subheader("Zusammenfassung")
    data = st.session_state.data
    missing = missing_keys(data, critical)
    if missing:
        st.warning(f"Es fehlen noch kritische Felder: {', '.join(missing)}")

    st.json(data)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💡 Follow-ups vorschlagen (LLM)", type="primary"):
            payload = {"lang": st.session_state.lang, "data": data, "missing": missing}
            try:
                res = ask_followups(
                    payload, model=st.session_state.model, vector_store_id=st.session_state.vector_store_id or None
                )
                st.session_state["followups"] = res
                st.success("Follow-ups aktualisiert.")
            except Exception as e:
                st.error(f"Follow-ups fehlgeschlagen: {e}")

    with col2:
        if st.session_state.get("followups"):
            st.write("**Vorgeschlagene Fragen:**")
            fu = st.session_state["followups"]
            for item in fu.get("questions", []):
                key = item.get("key")  # dot key, z.B. "requirements.hard_skills"
                q = item.get("question")
                if not key or not q:
                    continue
                st.markdown(f"**{q}**")
                val = st.text_input(f"Antwort für {key}", key=f"fu_{key}")
                if val:
                    set_in(data, key, val)

    st.divider()
    if missing:
        st.info("Bitte fülle die fehlenden kritischen Felder, um abzuschließen.")
    else:
        st.success("Alle kritischen Felder sind befüllt.")


# --- Haupt-Wizard-Runner ---
def run_wizard():
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
        ("Intro", _step_intro),
        ("Quelle", lambda: _step_source(schema)),
        ("Unternehmen", _step_company),
        ("Position", _step_position),
        ("Anforderungen", _step_requirements),
        ("Beschäftigung", _step_employment),
        ("Vergütung", _step_compensation),
        ("Prozess", _step_process),
        ("Summary", lambda: _step_summary(schema, critical)),
    ]

    # Headline
    st.markdown("### 🧭 Wizard")

    # Step Navigation (oben)
    st.progress((st.session_state.step + 1) / len(steps))
    st.caption("Klicke auf „Weiter“ oder navigiere direkt zu einem Schritt.")

    # Render current step
    label, renderer = steps[st.session_state.step]
    st.markdown(f"#### Schritt {st.session_state.step + 1} — {label}")
    renderer()

    # Bottom nav
    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if st.session_state.step > 0 and st.button("◀︎ Zurück", use_container_width=True):
            st.session_state.step -= 1
            st.rerun()
    with col_next:
        # Gating: auf Summary erst, ansonsten immer weiter
        if st.session_state.step < len(steps) - 1:
            if st.button("Weiter ▶︎", type="primary", use_container_width=True):
                st.session_state.step += 1
                st.rerun()
        else:
            st.button("Fertig", disabled=bool(missing_keys(st.session_state.data, critical)))
