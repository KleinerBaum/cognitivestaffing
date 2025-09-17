# wizard.py — Cognitive Needs Wizard (clean flow, schema-aligned)
from __future__ import annotations

import hashlib
import io
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List, Optional

import re
import streamlit as st

from utils.i18n import tr
from constants.keys import UIKeys, StateKeys
from utils.session import bind_textarea
from state.ensure_state import ensure_state
from ingest.extractors import extract_text_from_file, extract_text_from_url
from ingest.reader import clean_job_text
from ingest.heuristics import apply_basic_fallbacks
from utils.errors import display_error
from config_loader import load_json
from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill

# LLM/ESCO und Follow-ups
from openai_utils import (
    extract_with_function,  # nutzt deine neue Definition
    generate_interview_guide,
    generate_job_ad,
    refine_document,
)
from core.suggestions import get_benefit_suggestions, get_skill_suggestions
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from integrations.esco import search_occupation, enrich_skills
from components.stepper import render_stepper
from utils import build_boolean_search
from nlp.bias import scan_bias_language
from core.esco_utils import normalize_skills

ROOT = Path(__file__).parent
ensure_state()

WIZARD_TITLE = (
    "Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool"
)

OVERVIEW_STEP_INDEX = 1

REQUIRED_SUFFIX = " :red[*]"
REQUIRED_PREFIX = ":red[*] "

CEFR_LANGUAGE_LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2", "Native"]


def _format_language_level_option(option: str) -> str:
    """Return a localized label for the English level select box.

    Args:
        option: Raw option value from the CEFR options list.

    Returns:
        Translated label to render in the select box.
    """

    if option == "":
        return tr("Bitte Level wählen …", "Select level …")
    if option.lower() == "native":
        return tr("Muttersprachlich", "Native")
    return option


def next_step() -> None:
    """Advance the wizard to the next step."""

    current = st.session_state.get(StateKeys.STEP, 0)
    if current == 4:
        try:
            lang = st.session_state.get("lang", "en")
            reqs = st.session_state[StateKeys.PROFILE].get("requirements", {})
            for key in [
                "hard_skills_required",
                "hard_skills_optional",
                "soft_skills_required",
                "soft_skills_optional",
                "tools_and_technologies",
            ]:
                if key in reqs:
                    reqs[key] = normalize_skills(reqs.get(key, []), lang=lang)
        except Exception:
            pass
    st.session_state[StateKeys.STEP] = current + 1


def prev_step() -> None:
    """Return to the previous wizard step."""

    st.session_state[StateKeys.STEP] = max(
        0, st.session_state.get(StateKeys.STEP, 0) - 1
    )


def on_file_uploaded() -> None:
    """Handle file uploads and populate job posting text."""

    f = st.session_state.get(UIKeys.PROFILE_FILE_UPLOADER)
    if not f:
        return
    try:
        txt_raw = extract_text_from_file(f)
        txt = clean_job_text(txt_raw)
    except ValueError as e:
        msg = str(e).lower()
        if "unsupported file type" in msg:
            display_error(
                tr(
                    "Dieser Dateityp wird nicht unterstützt. Bitte laden Sie eine PDF-, DOCX- oder Textdatei hoch.",
                    "Unsupported file type. Please upload a PDF, DOCX, or text file.",
                ),
                str(e),
            )
        elif "file too large" in msg:
            display_error(
                tr(
                    "Datei ist zu groß. Maximale Größe: 20 MB.",
                    "File is too large. Maximum size: 20 MB.",
                ),
                str(e),
            )
        elif "invalid pdf" in msg:
            display_error(
                tr(
                    "Ungültige oder beschädigte PDF-Datei.",
                    "Invalid or corrupted PDF file.",
                ),
                str(e),
            )
        else:
            display_error(
                tr(
                    "Datei enthält keinen Text – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                    "File contains no text – you can also enter the information manually in the following steps.",
                ),
            )
        st.session_state["source_error"] = True
        return
    except RuntimeError as e:  # pragma: no cover - OCR
        display_error(
            tr(
                "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
                "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
            ),
            str(e),
        )
        st.session_state["source_error"] = True
        return
    except Exception as e:  # pragma: no cover - defensive
        display_error(
            tr(
                "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
                "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
            ),
            str(e),
        )
        st.session_state["source_error"] = True
        return
    if not txt.strip():
        display_error(
            tr(
                "Datei enthält keinen Text – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "File contains no text – you can also enter the information manually in the following steps.",
            ),
        )
        st.session_state["source_error"] = True
        return
    st.session_state["__prefill_profile_text__"] = txt
    st.session_state["__run_extraction__"] = True


def on_url_changed() -> None:
    """Fetch text from URL and populate job posting text."""

    url = st.session_state.get(UIKeys.PROFILE_URL_INPUT, "").strip()
    if not url:
        return
    if not re.match(r"^https?://[\w./-]+$", url):
        display_error(
            tr(
                "Ungültige URL – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Invalid URL – you can also enter the information manually in the following steps.",
            )
        )
        st.session_state["source_error"] = True
        return
    try:
        txt_raw = extract_text_from_url(url)
        txt = clean_job_text(txt_raw or "")
    except Exception as e:  # pragma: no cover - defensive
        display_error(
            tr(
                "URL konnte nicht geladen werden. Prüfen Sie Erreichbarkeit oder Firewall-Einstellungen.",
                "Failed to fetch URL. Check if the site is reachable or if access is blocked.",
            ),
            str(e),
        )
        st.session_state["source_error"] = True
        return
    if not txt or not txt.strip():
        display_error(
            tr(
                "Keine Textinhalte gefunden – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "No text content found – you can also enter the information manually in the following steps.",
            ),
        )
        st.session_state["source_error"] = True
        return
    st.session_state["__prefill_profile_text__"] = txt
    st.session_state["__run_extraction__"] = True


def _autodetect_lang(text: str) -> None:
    """Detect language from ``text`` and update session language."""

    if not text:
        return
    try:
        from langdetect import detect

        if detect(text).startswith("en"):
            st.session_state["lang"] = "en"
    except Exception:  # pragma: no cover - best effort
        pass


def _extract_and_summarize(text: str, schema: dict) -> None:
    """Run extraction on ``text`` and store profile, summary, and missing fields."""

    extracted = extract_with_function(text, schema, model=st.session_state.model)
    profile = coerce_and_fill(extracted)
    profile = apply_basic_fallbacks(profile, text)
    st.session_state[StateKeys.PROFILE] = profile.model_dump()
    title = profile.position.job_title or ""
    occ = search_occupation(title, st.session_state.lang or "en") if title else None
    if occ:
        profile.position.occupation_label = occ.get("preferredLabel") or ""
        profile.position.occupation_uri = occ.get("uri") or ""
        profile.position.occupation_group = occ.get("group") or ""
        skills = enrich_skills(occ.get("uri") or "", st.session_state.lang or "en")
        current_skills = set(profile.requirements.hard_skills_required or [])
        merged = sorted(current_skills.union(skills or []))
        profile.requirements.hard_skills_required = merged
    data = profile.model_dump()
    st.session_state[StateKeys.PROFILE] = data
    summary: dict[str, str] = {}
    if profile.position.job_title:
        summary[tr("Jobtitel", "Job title")] = profile.position.job_title
    if profile.company.name:
        summary[tr("Firma", "Company")] = profile.company.name
    if profile.location.primary_city:
        summary[tr("Ort", "Location")] = profile.location.primary_city
    sal_min = profile.compensation.salary_min
    sal_max = profile.compensation.salary_max
    if sal_min is not None or sal_max is not None:
        currency = profile.compensation.currency or ""
        if sal_min is not None and sal_max is not None:
            salary_str = f"{int(sal_min)}–{int(sal_max)} {currency}"
        else:
            value = sal_min if sal_min is not None else sal_max
            salary_str = f"{int(value)} {currency}" if value is not None else currency
        summary[tr("Gehaltsspanne", "Salary range")] = salary_str.strip()
    hard_total = len(profile.requirements.hard_skills_required) + len(
        profile.requirements.hard_skills_optional
    )
    if hard_total:
        summary[tr("Hard Skills", "Hard skills")] = str(hard_total)
    soft_total = len(profile.requirements.soft_skills_required) + len(
        profile.requirements.soft_skills_optional
    )
    if soft_total:
        summary[tr("Soft Skills", "Soft skills")] = str(soft_total)
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = summary
    missing: list[str] = []
    for field in CRITICAL_FIELDS:
        if not get_in(data, field, None):
            missing.append(field)
    st.session_state[StateKeys.EXTRACTION_MISSING] = missing
    if st.session_state.get("auto_reask"):
        try:
            round_num = st.session_state.get("auto_reask_round", 0) + 1
            st.session_state["auto_reask_round"] = round_num
            total_rounds = st.session_state.get("auto_reask_total", len(missing))
            st.session_state["auto_reask_total"] = total_rounds
            msg = tr(
                f"Generiere automatisch Anschlussfrage {round_num} von {total_rounds}...",
                f"Automatically generating follow-up {round_num} of {total_rounds}...",
            )
            with st.spinner(msg):
                payload = {
                    "data": profile.model_dump(),
                    "lang": st.session_state.lang,
                }
                followup_res = ask_followups(
                    payload,
                    model=st.session_state.model,
                    vector_store_id=st.session_state.vector_store_id or None,
                )
            done = set(
                st.session_state[StateKeys.PROFILE]
                .get("meta", {})
                .get("followups_answered", [])
            )
            st.session_state[StateKeys.FOLLOWUPS] = [
                q
                for q in followup_res.get("questions", [])
                if q.get("field") not in done
            ]
        except Exception:
            st.warning(
                tr(
                    "Konnte keine Anschlussfragen erzeugen.",
                    "Could not generate follow-ups automatically.",
                )
            )


def _maybe_run_extraction(schema: dict) -> None:
    """Trigger extraction when the corresponding flag is set in session state."""

    should_run = st.session_state.pop("__run_extraction__", False)
    if not should_run:
        return

    raw_input = st.session_state.get(StateKeys.RAW_TEXT, "") or ""
    raw_clean = clean_job_text(raw_input)
    if not raw_clean.strip():
        st.session_state["_analyze_attempted"] = True
        st.session_state.pop("__last_extracted_hash__", None)
        st.warning(
            tr(
                "Keine Daten erkannt – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "No data detected – you can also enter the information manually in the following steps.",
            )
        )
        return

    digest = hashlib.sha256(raw_clean.encode("utf-8")).hexdigest()
    if digest == st.session_state.get("__last_extracted_hash__"):
        st.session_state[StateKeys.STEP] = OVERVIEW_STEP_INDEX
        st.rerun()
        return

    st.session_state["_analyze_attempted"] = True
    st.session_state[StateKeys.RAW_TEXT] = raw_clean
    st.session_state["__last_extracted_hash__"] = digest
    _autodetect_lang(raw_clean)
    try:
        _extract_and_summarize(raw_clean, schema)
        st.session_state[StateKeys.STEP] = OVERVIEW_STEP_INDEX
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
        st.session_state[StateKeys.EXTRACTION_MISSING] = []
        st.rerun()
    except Exception as exc:
        st.session_state.pop("__last_extracted_hash__", None)
        display_error(
            tr(
                "Automatische Extraktion fehlgeschlagen",
                "Automatic extraction failed",
            ),
            str(exc),
        )


def _skip_source() -> None:
    """Skip source step and initialize an empty profile."""

    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.RAW_TEXT] = ""
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
    st.session_state[StateKeys.EXTRACTION_MISSING] = []
    st.session_state.pop("_analyze_attempted", None)
    st.session_state.pop("__last_extracted_hash__", None)
    st.session_state[StateKeys.STEP] = OVERVIEW_STEP_INDEX
    st.rerun()


def _on_logo_uploaded() -> None:
    """Persist the uploaded company logo in session state."""

    uploader = st.session_state.get(UIKeys.COMPANY_LOGO)
    if uploader is None:
        st.session_state.pop("company_logo", None)
        return
    st.session_state["company_logo"] = uploader.read()


FIELD_LABELS: dict[str, tuple[str, str]] = {
    "company.name": ("Firmenname", "Company Name"),
    "position.job_title": ("Jobtitel", "Job Title"),
    "position.role_summary": ("Rollenbeschreibung", "Role Summary"),
    "location.country": ("Land", "Country"),
    "requirements.hard_skills_required": (
        "Pflicht-Hard-Skills",
        "Required Hard Skills",
    ),
    "requirements.soft_skills_required": (
        "Pflicht-Soft-Skills",
        "Required Soft Skills",
    ),
}


def _field_label(path: str) -> str:
    """Return localized label for a schema field path.

    Args:
        path: Dot-separated schema field path.

    Returns:
        Localized label if known, otherwise a humanized version of ``path``.
    """

    if path in FIELD_LABELS:
        de, en = FIELD_LABELS[path]
        return tr(de, en)
    auto = path.replace(".", " ").replace("_", " ")
    return tr(auto.title(), auto.title())


def _has_value(value) -> bool:
    """Return ``True`` if a flattened value should be shown in the overview."""

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    return True


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


def _render_overview_field(path: str, data: dict) -> None:
    """Render an editable field for the overview step."""

    current_value = get_in(data, path)
    label = _field_label(path)
    schema_hint = tr("Schema-Schlüssel: {}", "Schema key: {}").format(path)
    key_base = f"ui.overview.{path}"

    if isinstance(current_value, bool):
        checked = st.checkbox(
            label,
            value=bool(current_value),
            key=key_base,
            help=schema_hint,
        )
        if checked != current_value:
            _update_profile(path, checked)
        st.caption(schema_hint)
        return

    if isinstance(current_value, list):
        if all(isinstance(item, str) for item in current_value):
            serialized = "\n".join(item for item in current_value if item is not None)
            text_value = st.text_area(
                label,
                value=serialized,
                key=key_base,
                help=tr(
                    "Ein Eintrag pro Zeile. {}",
                    "One entry per line. {}",
                ).format(schema_hint),
            )
            new_items = [
                line.strip() for line in text_value.splitlines() if line.strip()
            ]
            if new_items != current_value:
                _update_profile(path, new_items)
        else:
            serialized = json.dumps(current_value, ensure_ascii=False, indent=2)
            text_value = st.text_area(
                label,
                value=serialized,
                key=key_base,
                help=tr(
                    "Komplexe Werte im JSON-Format bearbeiten. {}",
                    "Edit complex values using JSON syntax. {}",
                ).format(schema_hint),
            )
            stripped = text_value.strip()
            if not stripped:
                empty_list: list[Any] = []
                if empty_list != current_value:
                    _update_profile(path, empty_list)
            else:
                try:
                    parsed_value = json.loads(stripped)
                except json.JSONDecodeError:
                    st.warning(
                        tr(
                            "Ungültiges JSON – Änderungen wurden nicht übernommen.",
                            "Invalid JSON input – changes were not applied.",
                        ),
                        icon="⚠️",
                    )
                else:
                    if parsed_value != current_value:
                        _update_profile(path, parsed_value)
        st.caption(schema_hint)
        return

    if isinstance(current_value, (int, float)) and not isinstance(current_value, bool):
        text_value = st.text_input(
            label,
            value=str(current_value),
            key=key_base,
            help=schema_hint,
        )
        stripped = text_value.strip()
        if not stripped:
            if current_value is not None:
                _update_profile(path, None)
        else:
            target_type = int if isinstance(current_value, int) else float
            try:
                parsed = target_type(stripped)
            except ValueError:
                st.warning(
                    tr(
                        "Ungültige Zahl – bitte prüfen Sie Ihre Eingabe.",
                        "Invalid number – please check your input.",
                    ),
                    icon="⚠️",
                )
            else:
                if parsed != current_value:
                    _update_profile(path, parsed)
        st.caption(schema_hint)
        return

    text_widget = (
        st.text_area
        if isinstance(current_value, str)
        and (len(current_value) > 120 or "\n" in current_value)
        else st.text_input
    )
    text_value = text_widget(
        label,
        value=current_value if isinstance(current_value, str) else str(current_value),
        key=key_base,
        help=schema_hint,
    )
    if isinstance(current_value, str):
        candidate = text_value if text_value.strip() else None
    else:
        candidate = text_value.strip() if text_value.strip() else None
    if candidate != current_value:
        _update_profile(path, candidate)
    st.caption(schema_hint)


def _render_followup_question(q: dict, data: dict) -> None:
    """Render a follow-up question with optional suggestion chips."""

    field = q.get("field", "")
    prompt = q.get("question", "")
    suggestions = q.get("suggestions") or []
    key = f"fu_{field}"
    anchor = f"anchor_{key}"
    st.markdown(f"<div id='{anchor}'></div>", unsafe_allow_html=True)
    if key not in st.session_state:
        st.session_state[key] = ""
    if q.get("priority") == "critical":
        st.markdown(f"{REQUIRED_PREFIX}**{prompt}**")
    else:
        st.markdown(f"**{prompt}**")
    if suggestions:
        cols = st.columns(len(suggestions))
        for i, (col, sug) in enumerate(zip(cols, suggestions)):
            if col.button(sug, key=f"{key}_opt_{i}"):
                st.session_state[key] = sug
    st.text_input("", key=key)
    if q.get("priority") == "critical":
        st.toast(
            tr("Neue kritische Anschlussfrage", "New critical follow-up"), icon="⚠️"
        )
        st.markdown(
            f"<script>var el=document.getElementById('{anchor}').nextElementSibling;el.classList.add('fu-highlight');el.scrollIntoView({{behavior:'smooth',block:'center'}});</script>",
            unsafe_allow_html=True,
        )
    ans = st.session_state.get(key, "")
    if ans:
        set_in(data, field, ans)
        completed = data.setdefault("meta", {}).setdefault("followups_answered", [])
        if field not in completed:
            completed.append(field)
        st.session_state[StateKeys.FOLLOWUPS].remove(q)


def _render_followups_for_section(prefixes: Iterable[str], data: dict) -> None:
    """Render heading and follow-up questions matching ``prefixes``."""

    followups = [
        q
        for q in st.session_state.get(StateKeys.FOLLOWUPS, [])
        if any(q.get("field", "").startswith(p) for p in prefixes)
    ]
    if followups:
        st.markdown(
            tr(
                "Der Assistent hat Anschlussfragen, um fehlende Angaben zu ergänzen:",
                "The assistant has generated follow-up questions to help fill in missing info:",
            )
        )
        for q in list(followups):
            _render_followup_question(q, data)


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


def _slugify_label(label: str) -> str:
    """Convert a widget label into a slug suitable for state keys.

    Args:
        label: Original widget label.

    Returns:
        Slugified representation of the label.
    """

    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").lower()
    return cleaned or "field"


def _unique_normalized(values: Iterable[str] | None) -> list[str]:
    """Return values without duplicates, normalized for comparison.

    Args:
        values: Iterable of strings that may include duplicates or blanks.

    Returns:
        List of trimmed values without case-insensitive duplicates.
    """

    seen: set[str] = set()
    result: list[str] = []
    if not values:
        return result
    for value in values:
        if value is None:
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(cleaned)
    return result


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


def missing_keys(
    data: dict, critical: List[str], ignore: Optional[set[str]] = None
) -> List[str]:
    """Identify required keys that are missing or empty.

    Args:
        data: Vacancy data to inspect.
        critical: List of required dot-separated keys.
        ignore: Optional set of keys to exclude from the result.

    Returns:
        List of keys that are absent or have empty values.
    """

    flat = flatten(data)
    ignore = ignore or set()
    return [
        k
        for k in critical
        if k not in ignore and ((k not in flat) or (flat[k] in (None, "", [], {})))
    ]


# --- UI-Komponenten ---
def _chip_multiselect(label: str, options: List[str], values: List[str]) -> List[str]:
    """Render a multiselect with chip-like UX and free-text additions.

    Args:
        label: UI label for the widget.
        options: Available options coming from profile data or suggestions.
        values: Initially selected options.

    Returns:
        Updated list of selections from the user.
    """

    slug = _slugify_label(label)
    ms_key = f"ms_{label}"
    options_key = f"ui.chip_options.{slug}"
    input_key = f"ui.chip_input.{slug}"
    button_key = f"ui.chip_add_btn.{slug}"

    base_options = _unique_normalized(options)
    base_values = _unique_normalized(values)

    current_selection = _unique_normalized(st.session_state.get(ms_key, []))
    if current_selection:
        base_values = current_selection

    stored_options = _unique_normalized(st.session_state.get(options_key, []))
    available_options = _unique_normalized(stored_options + base_options + base_values)
    available_options = sorted(available_options, key=str.casefold)
    st.session_state[options_key] = available_options

    input_col, button_col = st.columns([3, 1])
    new_entry = input_col.text_input(
        tr("Neuen Wert hinzufügen", "Add new value"),
        key=input_key,
        placeholder=tr("Neuen Wert hinzufügen …", "Add new value …"),
        label_visibility="collapsed",
    )
    add_clicked = button_col.button(
        tr("Hinzufügen", "Add"),
        key=button_key,
        use_container_width=True,
    )

    if add_clicked:
        candidate = new_entry.strip()
        if candidate:
            available_options = sorted(
                _unique_normalized(available_options + [candidate]),
                key=str.casefold,
            )
            st.session_state[options_key] = available_options
            base_values = _unique_normalized(base_values + [candidate])
            st.session_state[ms_key] = base_values

    default_selection = _unique_normalized(st.session_state.get(ms_key, base_values))
    selection = st.multiselect(
        label,
        options=available_options,
        default=default_selection,
        key=ms_key,
    )
    return _unique_normalized(selection)


# --- Step-Renderers ---
def _step_onboarding(schema: dict) -> None:
    """Render onboarding with language choice and ingestion options."""

    _maybe_run_extraction(schema)

    lang_options = {"de": "Deutsch", "en": "English"}
    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    def _on_lang_change() -> None:
        st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    st.radio(
        "🌐 Sprache / Language",
        options=list(lang_options.keys()),
        key=UIKeys.LANG_SELECT,
        horizontal=True,
        format_func=lambda key: lang_options[key],
        on_change=_on_lang_change,
    )

    st.markdown(
        "### "
        + tr(
            "Willkommen beim Cognitive Needs Wizard",
            "Welcome to the Cognitive Needs wizard",
        )
    )
    st.write(
        tr(
            "Dieser Assistent begleitet Sie Schritt für Schritt durch die Erstellung eines strukturierten Stellenprofils.",
            "This assistant guides you step by step towards a structured job profile.",
        )
    )

    if "ui.skip_intro" not in st.session_state:
        st.session_state["ui.skip_intro"] = st.session_state.get("skip_intro", False)

    def _on_skip_intro() -> None:
        st.session_state["skip_intro"] = st.session_state["ui.skip_intro"]

    show_intro = not st.session_state.get("skip_intro", False)
    if show_intro:
        st.write(
            tr(
                "Laden Sie eine Stellenanzeige oder geben Sie die wichtigsten Informationen manuell ein.",
                "Upload an existing job post or enter the most important information manually.",
            )
        )
        advantages_md = tr(
            (
                "- Strukturierte Datenerfassung ohne Informationsverlust\n"
                "- Automatische Vorbefüllung aus Text, Datei oder URL\n"
                "- Mehrsprachige Oberfläche (DE/EN)\n"
                "- Direkter Zugriff auf Benefits, Prozesse und Folgefragen"
            ),
            (
                "- Structured data capture without information loss\n"
                "- Automatic prefill from text, files or URLs\n"
                "- Bilingual interface (DE/EN)\n"
                "- Direct access to benefits, processes and follow-ups"
            ),
        )
        st.markdown(advantages_md)
    st.checkbox(
        tr("Intro künftig überspringen", "Don't show this intro again"),
        key="ui.skip_intro",
        on_change=_on_skip_intro,
    )

    method_options = [
        ("text", tr("Text eingeben", "Enter text")),
        ("file", tr("Datei hochladen", "Upload file")),
        ("url", tr("URL eingeben", "Enter URL")),
    ]
    method_labels = {value: label for value, label in method_options}
    if UIKeys.INPUT_METHOD not in st.session_state:
        st.session_state[UIKeys.INPUT_METHOD] = "text"

    col_main, col_side = st.columns((3, 2))

    with col_main:
        st.markdown("#### " + tr("Eingabemethode wählen", "Choose your input method"))
        st.radio(
            tr("Wie möchten Sie starten?", "How would you like to start?"),
            options=list(method_labels.keys()),
            key=UIKeys.INPUT_METHOD,
            format_func=method_labels.__getitem__,
            horizontal=True,
        )

        if st.session_state.pop("source_error", False):
            st.info(
                tr(
                    "Es gab ein Problem beim Import. Sie können die Angaben auch manuell ergänzen.",
                    "There was an issue with the import. You can still fill in the details manually.",
                )
            )

        prefill = st.session_state.pop("__prefill_profile_text__", None)
        if prefill is not None:
            st.session_state[UIKeys.PROFILE_TEXT_INPUT] = prefill
            st.session_state[StateKeys.RAW_TEXT] = prefill

        method = st.session_state[UIKeys.INPUT_METHOD]
        if method == "text":
            bind_textarea(
                tr("Jobtext", "Job text"),
                UIKeys.PROFILE_TEXT_INPUT,
                StateKeys.RAW_TEXT,
                placeholder=tr(
                    "Fügen Sie den Text Ihrer Stellenanzeige ein …",
                    "Paste the text of your job posting …",
                ),
                help=tr(
                    "Der Text wird analysiert und relevante Felder automatisch befüllt.",
                    "The text will be analysed to prefill relevant fields automatically.",
                ),
            )
            analyze_disabled = not bool(
                (st.session_state.get(StateKeys.RAW_TEXT, "") or "").strip()
            )
            if st.button(
                tr("Analyse starten", "Start analysis"),
                type="primary",
                disabled=analyze_disabled,
            ):
                st.session_state["__run_extraction__"] = True
                st.rerun()
            if analyze_disabled:
                st.caption(
                    tr(
                        "Bitte geben Sie zunächst Text ein.",
                        "Please enter some text first.",
                    )
                )
        elif method == "file":
            st.file_uploader(
                tr(
                    "Stellenanzeige hochladen (PDF/DOCX/TXT)",
                    "Upload job posting (PDF/DOCX/TXT)",
                ),
                type=["pdf", "docx", "txt"],
                key=UIKeys.PROFILE_FILE_UPLOADER,
                on_change=on_file_uploaded,
                help=tr(
                    "Nach dem Upload startet die Analyse automatisch.",
                    "Analysis starts automatically after the upload finishes.",
                ),
            )
        else:
            st.text_input(
                tr("Öffentliche Stellenanzeigen-URL", "Public job posting URL"),
                key=UIKeys.PROFILE_URL_INPUT,
                on_change=on_url_changed,
                placeholder="https://example.com/job",
                help=tr(
                    "Die URL muss ohne Login erreichbar sein.",
                    "The URL must be accessible without authentication.",
                ),
            )

        skip_clicked = st.button(
            tr("Ohne Vorlage fortfahren", "Continue without template"),
            type="secondary",
        )
        if skip_clicked:
            _skip_source()

        st.info(
            tr(
                "Nach erfolgreichem Import gelangen Sie automatisch zur Übersicht aller erkannten Felder.",
                "After a successful import you'll be redirected to the overview of all detected fields.",
            )
        )

    with col_side:
        st.markdown("#### " + tr("Branding", "Branding"))
        st.file_uploader(
            tr("Optional: Firmenlogo", "Optional: Company logo"),
            type=["png", "jpg", "jpeg", "svg", "webp"],
            key=UIKeys.COMPANY_LOGO,
            on_change=_on_logo_uploaded,
        )
        logo_bytes = st.session_state.get("company_logo")
        if logo_bytes:
            st.image(logo_bytes, width=160)
        st.caption(
            tr(
                "Logo und Theme wirken sich auf exportierte Inhalte aus. Den Dark Mode können Sie in der Seitenleiste umschalten.",
                "Logo and theme impact exported artefacts. Toggle dark mode via the sidebar controls.",
            )
        )


def _step_overview(_schema: dict, _critical: list[str]) -> None:
    """Display an editable overview of populated fields."""

    st.subheader(tr("Übersicht", "Overview"))
    st.caption(
        tr(
            "Bearbeiten Sie vorhandene Werte direkt hier. Änderungen werden automatisch übernommen.",
            "Edit existing values directly here. Changes are applied across the wizard.",
        )
    )

    data = st.session_state.get(StateKeys.PROFILE, {}) or {}
    flat = flatten(data)

    filled_fields = [
        field
        for field, value in sorted(flat.items())
        if not field.startswith("meta.") and _has_value(value)
    ]

    if not filled_fields:
        st.info(
            tr(
                "Noch keine Daten vorhanden – starten Sie mit einer Vorlage oder füllen Sie die nächsten Schritte manuell aus.",
                "No data available yet – upload a template or continue with the next steps to fill the fields manually.",
            )
        )
        return

    for index, field in enumerate(filled_fields):
        _render_overview_field(field, data)
        if index < len(filled_fields) - 1:
            st.divider()


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
    missing_here = [
        f
        for f in get_missing_critical_fields(max_section=1)
        if FIELD_SECTION_MAP.get(f) == 1
    ]

    label_company = tr("Firma", "Company")
    if "company.name" in missing_here:
        label_company += REQUIRED_SUFFIX
    data["company"]["name"] = st.text_input(
        label_company,
        value=data["company"].get("name", ""),
        placeholder=tr("z. B. ACME GmbH", "e.g., ACME Corp"),
        help=tr("Offizieller Firmenname", "Official company name"),
    )
    if "company.name" in missing_here and not data["company"]["name"]:
        st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

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

        logo_file = st.file_uploader(
            tr("Firmenlogo", "Company Logo"),
            type=["png", "jpg"],
            key="ui.company_logo",
        )
        if logo_file:
            st.session_state["company_logo"] = logo_file.getvalue()
            st.image(logo_file)
        data["company"]["brand_keywords"] = st.text_input(
            tr("Brand-Ton oder Keywords", "Brand tone or keywords"),
            value=data["company"].get("brand_keywords", ""),
            key="ui.company.brand_keywords",
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
    _render_followups_for_section(("company.",), data)


_step_company.handled_fields = ["company.name"]  # type: ignore[attr-defined]


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
            value=person.get("email") or "",
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

    st.subheader(tr("Basisdaten", "Basic data"))
    st.caption(
        tr(
            "Kerninformationen zur Rolle, zum Standort und Rahmenbedingungen erfassen.",
            "Capture key information about the role, location and context.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]
    missing_here = [
        f
        for f in get_missing_critical_fields(max_section=2)
        if FIELD_SECTION_MAP.get(f) == 2
    ]

    c1, c2 = st.columns(2)
    label_title = tr("Jobtitel", "Job title")
    if "position.job_title" in missing_here:
        label_title += REQUIRED_SUFFIX
    data["position"]["job_title"] = c1.text_input(
        label_title,
        value=data["position"].get("job_title", ""),
        placeholder=tr("z. B. Data Scientist", "e.g., Data Scientist"),
    )
    if "position.job_title" in missing_here and not data["position"]["job_title"]:
        c1.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

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
    label_summary = tr("Rollen-Summary", "Role summary")
    if "position.role_summary" in missing_here:
        label_summary += REQUIRED_SUFFIX
    data["position"]["role_summary"] = c6.text_area(
        label_summary,
        value=data["position"].get("role_summary", ""),
        height=120,
    )
    if "position.role_summary" in missing_here and not data["position"]["role_summary"]:
        c6.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    c7, c8 = st.columns(2)
    data["location"]["primary_city"] = c7.text_input(
        tr("Stadt", "City"),
        value=data.get("location", {}).get("primary_city", ""),
        placeholder=tr("z. B. Berlin", "e.g., Berlin"),
    )
    label_country = tr("Land", "Country")
    if "location.country" in missing_here:
        label_country += REQUIRED_SUFFIX
    data["location"]["country"] = c8.text_input(
        label_country,
        value=data.get("location", {}).get("country", ""),
        placeholder=tr("z. B. DE", "e.g., DE"),
    )
    if "location.country" in missing_here and not data["location"].get("country"):
        c8.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    c9, c10, c11 = st.columns(3)
    data["meta"]["target_start_date"] = c9.text_input(
        tr("Gewünschtes Startdatum", "Desired start date"),
        value=data["meta"].get("target_start_date", ""),
        placeholder="YYYY-MM-DD",
    )
    data["meta"]["application_deadline"] = c10.text_input(
        tr("Bewerbungsschluss", "Application deadline"),
        value=data["meta"].get("application_deadline", ""),
        placeholder="YYYY-MM-DD",
    )
    data["position"]["supervises"] = c11.number_input(
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
    _render_followups_for_section(("position.", "location.", "meta."), data)


_step_position.handled_fields = [  # type: ignore[attr-defined]
    "position.job_title",
    "position.role_summary",
    "location.country",
]


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
    missing_here = [
        f
        for f in get_missing_critical_fields(max_section=3)
        if FIELD_SECTION_MAP.get(f) == 3
    ]

    # LLM-basierte Skill-Vorschläge abrufen
    job_title = (data.get("position", {}).get("job_title", "") or "").strip()
    stored = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})
    if job_title and stored.get("_title") != job_title:
        sugg, err = get_skill_suggestions(
            job_title,
            lang=st.session_state.get("lang", "en"),
        )
        if err or not any(sugg.values()):
            st.warning(
                tr(
                    "Skill-Vorschläge nicht verfügbar (API-Fehler)",
                    "Skill suggestions not available (API error)",
                )
            )
            if err and st.session_state.get("debug"):
                st.session_state["skill_suggest_error"] = err
        stored = {"_title": job_title, **sugg}
        st.session_state[StateKeys.SKILL_SUGGESTIONS] = stored
    suggestions = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})

    label_hard_req = tr("Hard Skills (Muss)", "Hard Skills (Must-have)")
    if "requirements.hard_skills_required" in missing_here:
        label_hard_req += REQUIRED_SUFFIX
    data["requirements"]["hard_skills_required"] = _chip_multiselect(
        label_hard_req,
        options=data["requirements"].get("hard_skills_required", []),
        values=data["requirements"].get("hard_skills_required", []),
    )
    if "requirements.hard_skills_required" in missing_here and not data[
        "requirements"
    ].get("hard_skills_required"):
        st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    data["requirements"]["hard_skills_optional"] = _chip_multiselect(
        tr("Hard Skills (Nice-to-have)", "Hard Skills (Nice-to-have)"),
        options=data["requirements"].get("hard_skills_optional", []),
        values=data["requirements"].get("hard_skills_optional", []),
    )
    label_soft_req = tr("Soft Skills (Muss)", "Soft Skills (Must-have)")
    if "requirements.soft_skills_required" in missing_here:
        label_soft_req += REQUIRED_SUFFIX
    data["requirements"]["soft_skills_required"] = _chip_multiselect(
        label_soft_req,
        options=data["requirements"].get("soft_skills_required", []),
        values=data["requirements"].get("soft_skills_required", []),
    )
    if "requirements.soft_skills_required" in missing_here and not data[
        "requirements"
    ].get("soft_skills_required"):
        st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    data["requirements"]["soft_skills_optional"] = _chip_multiselect(
        tr("Soft Skills (Nice-to-have)", "Soft Skills (Nice-to-have)"),
        options=data["requirements"].get("soft_skills_optional", []),
        values=data["requirements"].get("soft_skills_optional", []),
    )
    data["requirements"]["tools_and_technologies"] = _chip_multiselect(
        tr("Tools & Tech", "Tools & Tech"),
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
    current_language_level = data["requirements"].get("language_level_english") or ""
    language_level_options = list(CEFR_LANGUAGE_LEVELS)
    if current_language_level and current_language_level not in language_level_options:
        language_level_options.append(current_language_level)
    data["requirements"]["language_level_english"] = st.selectbox(
        tr("Englischniveau", "English level"),
        options=language_level_options,
        index=(
            language_level_options.index(current_language_level)
            if current_language_level in language_level_options
            else 0
        ),
        format_func=_format_language_level_option,
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
    _render_followups_for_section(("requirements.",), data)


_step_requirements.handled_fields = [  # type: ignore[attr-defined]
    "requirements.hard_skills_required",
    "requirements.soft_skills_required",
]


def _build_field_section_map() -> dict[str, int]:
    """Derive mapping of schema fields to wizard sections.

    Each step declares the fields it handles via ``handled_fields``. This
    function iterates over the step order and builds a reverse lookup to avoid
    mismatches between UI steps and critical field checks.

    Returns:
        Mapping of field paths to section numbers.
    """

    ordered_steps = [_step_company, _step_position, _step_requirements]
    mapping: dict[str, int] = {}
    for idx, step in enumerate(ordered_steps, start=1):
        for field in getattr(step, "handled_fields", []):
            mapping[field] = idx
    return mapping


FIELD_SECTION_MAP = _build_field_section_map()


def get_missing_critical_fields(*, max_section: int | None = None) -> list[str]:
    """Return critical fields missing from state or profile data.

    Args:
        max_section: Optional highest section number to inspect.

    Returns:
        List of missing critical field paths.
    """

    missing: list[str] = []
    profile_data = st.session_state.get(StateKeys.PROFILE, {})
    for field in CRITICAL_FIELDS:
        if max_section is not None and FIELD_SECTION_MAP.get(field, 0) > max_section:
            continue
        value = st.session_state.get(field)
        if not value:
            value = get_in(profile_data, field, None)
        if not value:
            missing.append(field)

    for q in st.session_state.get(StateKeys.FOLLOWUPS, []):
        if q.get("priority") == "critical":
            missing.append(q.get("field", ""))
    return missing


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

    c7, c8, c9 = st.columns(3)
    data["employment"]["overtime_expected"] = c7.toggle(
        tr("Überstunden?", "Overtime expected?"),
        value=bool(data["employment"].get("overtime_expected")),
    )
    data["employment"]["security_clearance_required"] = c8.toggle(
        tr("Sicherheitsüberprüfung?", "Security clearance required?"),
        value=bool(data["employment"].get("security_clearance_required")),
    )
    data["employment"]["shift_work"] = c9.toggle(
        tr("Schichtarbeit?", "Shift work?"),
        value=bool(data["employment"].get("shift_work")),
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
    _render_followups_for_section(("employment.",), data)


def _step_compensation():
    """Render the compensation and benefits step.

    Returns:
        None
    """

    st.subheader(tr("Leistungen & Benefits", "Rewards & Benefits"))
    st.caption(
        tr(
            "Gehaltsspanne und Zusatzleistungen erfassen.",
            "Capture salary range and benefits.",
        )
    )
    data = st.session_state[StateKeys.PROFILE]

    stored_min = data["compensation"].get("salary_min")
    stored_max = data["compensation"].get("salary_max")
    default_min = int(stored_min) if stored_min else 50000
    default_max = int(stored_max) if stored_max else 70000

    c_salary_min, c_salary_max = st.columns(2)
    salary_min = c_salary_min.number_input(
        tr("Gehalt von", "Salary from"),
        min_value=0,
        max_value=500000,
        value=default_min,
        step=1000,
        format="%i",
    )
    salary_max = c_salary_max.number_input(
        tr("Gehalt bis", "Salary to"),
        min_value=0,
        max_value=500000,
        value=default_max,
        step=1000,
        format="%i",
    )
    data["compensation"]["salary_min"] = int(salary_min)
    data["compensation"]["salary_max"] = int(salary_max)
    data["compensation"]["salary_provided"] = bool(salary_min or salary_max)

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
    sugg_benefits = st.session_state.get(StateKeys.BENEFIT_SUGGESTIONS, [])
    benefit_options = sorted(
        set(
            preset_benefits.get(lang, [])
            + data["compensation"].get("benefits", [])
            + sugg_benefits
        )
    )
    data["compensation"]["benefits"] = _chip_multiselect(
        "Benefits",
        options=benefit_options,
        values=data["compensation"].get("benefits", []),
    )

    if st.button("💡 " + tr("Benefits vorschlagen", "Suggest Benefits")):
        job_title = data.get("position", {}).get("job_title", "")
        industry = data.get("company", {}).get("industry", "")
        existing = "\n".join(data["compensation"].get("benefits", []))
        new_sugg, err = get_benefit_suggestions(
            job_title,
            industry,
            existing,
            lang=lang,
        )
        if err or not new_sugg:
            st.warning(
                tr(
                    "Benefit-Vorschläge nicht verfügbar (API-Fehler)",
                    "Benefit suggestions not available (API error)",
                )
            )
            if err and st.session_state.get("debug"):
                st.session_state["benefit_suggest_error"] = err
        if new_sugg:
            st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = sorted(
                set(sugg_benefits + new_sugg)
            )
            st.rerun()

    # Inline follow-up questions for Compensation section
    _render_followups_for_section(("compensation.",), data)


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
    _render_followups_for_section(("process.",), st.session_state[StateKeys.PROFILE])


def _summary_company() -> None:
    """Editable summary tab for company information."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    name = c1.text_input(
        tr("Firma", "Company") + REQUIRED_SUFFIX,
        value=data["company"].get("name", ""),
        key="ui.summary.company.name",
        help=tr("Dieses Feld ist erforderlich", "This field is required"),
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
    brand = st.text_input(
        tr("Brand-Ton oder Keywords", "Brand tone or keywords"),
        value=data["company"].get("brand_keywords", ""),
        key="ui.summary.company.brand_keywords",
    )
    logo_bytes = st.session_state.get("company_logo")
    if logo_bytes:
        st.image(logo_bytes, width=120)

    _update_profile("company.name", name)
    _update_profile("company.industry", industry)
    _update_profile("company.hq_location", hq)
    _update_profile("company.size", size)
    _update_profile("company.website", website)
    _update_profile("company.mission", mission)
    _update_profile("company.culture", culture)
    _update_profile("company.brand_keywords", brand)


def _summary_position() -> None:
    """Editable summary tab for position details."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    job_title = c1.text_input(
        tr("Jobtitel", "Job title") + REQUIRED_SUFFIX,
        value=data["position"].get("job_title", ""),
        key="ui.summary.position.job_title",
        help=tr("Dieses Feld ist erforderlich", "This field is required"),
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
        tr("Rollen-Summary", "Role summary") + REQUIRED_SUFFIX,
        value=data["position"].get("role_summary", ""),
        height=120,
        key="ui.summary.position.role_summary",
        help=tr("Dieses Feld ist erforderlich", "This field is required"),
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


def _step_summary(schema: dict, _critical: list[str]):
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
    completed = set(data.get("meta", {}).get("followups_answered", []))
    missing = missing_keys(data, _critical, ignore=completed)

    tabs = st.tabs(
        [
            tr("Unternehmen", "Company"),
            tr("Basisdaten", "Basic info"),
            tr("Anforderungen", "Requirements"),
            tr("Beschäftigung", "Employment"),
            tr("Leistungen & Benefits", "Rewards & Benefits"),
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
        file_name="cognitive_needs_profile.json",
        mime="application/json",
    )

    usage = st.session_state.get(StateKeys.USAGE)
    if usage:
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        total_tok = in_tok + out_tok
        label = tr("Verbrauchte Tokens", "Tokens used")
        st.caption(f"{label}: {in_tok} + {out_tok} = {total_tok}")

    tone_presets = load_json("tone_presets.json", {}) or {}
    tone_options = tone_presets.get(st.session_state.lang, {})
    tone_labels = {
        "formal": tr("Formell", "Formal"),
        "casual": tr("Locker", "Casual"),
        "creative": tr("Kreativ", "Creative"),
        "diversity_focused": tr("Diversität im Fokus", "Diversity-Focused"),
    }
    if UIKeys.TONE_SELECT not in st.session_state:
        st.session_state[UIKeys.TONE_SELECT] = "formal"
    selected_tone = st.selectbox(
        tr("Interviewleitfaden-Ton", "Interview Guide Tone"),
        options=list(tone_options.keys()),
        format_func=lambda k: tone_labels.get(k, k),
        key=UIKeys.TONE_SELECT,
    )
    st.session_state["tone"] = tone_options.get(selected_tone)

    if UIKeys.NUM_QUESTIONS not in st.session_state:
        st.session_state[UIKeys.NUM_QUESTIONS] = 5
    st.slider(
        tr("Anzahl Interviewfragen", "Number of Interview Questions"),
        min_value=3,
        max_value=10,
        key=UIKeys.NUM_QUESTIONS,
    )

    with st.expander(tr("Erweiterte Optionen", "Advanced Options")):
        audience_labels = {
            "general": tr("Allgemein", "General"),
            "technical": tr("Technisch", "Technical"),
            "HR": "HR",
        }
        if UIKeys.AUDIENCE_SELECT not in st.session_state:
            st.session_state[UIKeys.AUDIENCE_SELECT] = "general"
        st.selectbox(
            tr("Zielgruppe", "Guide Audience"),
            list(audience_labels.keys()),
            format_func=lambda k: audience_labels[k],
            key=UIKeys.AUDIENCE_SELECT,
        )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button(tr("📝 Stellenanzeige (Entwurf)", "📝 Job Ad (Draft)")):
            try:
                job_ad_md = generate_job_ad(data, tone=st.session_state.get("tone"))
                st.session_state[StateKeys.JOB_AD_MD] = job_ad_md
                findings = scan_bias_language(job_ad_md, st.session_state.lang)
                st.session_state[StateKeys.BIAS_FINDINGS] = findings
            except Exception as e:
                st.error(
                    tr(
                        "Job Ad Generierung fehlgeschlagen",
                        "Job ad generation failed",
                    )
                    + f": {e}"
                )

    with col_b:
        if st.button(tr("🔎 Boolean String", "🔎 Boolean String")):
            st.session_state[StateKeys.BOOLEAN_STR] = build_boolean_search(data)

    with col_c:
        selected_num = st.session_state.get(UIKeys.NUM_QUESTIONS, 5)
        audience = st.session_state.get(UIKeys.AUDIENCE_SELECT, "general")
        if st.button(tr("🗂️ Interviewleitfaden", "🗂️ Interview Guide")):
            try:
                profile = NeedAnalysisProfile(**data)
                extras = (
                    len(profile.requirements.hard_skills_required)
                    + len(profile.requirements.hard_skills_optional)
                    + len(profile.requirements.soft_skills_required)
                    + len(profile.requirements.soft_skills_optional)
                    + (1 if profile.company.culture else 0)
                )
                if selected_num + extras > 15:
                    st.warning(
                        tr(
                            "Viele Fragen könnten zu hohen Token-Kosten führen.",
                            "A high number of questions may increase token usage.",
                        )
                    )
                guide_md = generate_interview_guide(
                    job_title=profile.position.job_title or "",
                    responsibilities="\n".join(profile.responsibilities.items),
                    hard_skills=profile.requirements.hard_skills_required
                    + profile.requirements.hard_skills_optional,
                    soft_skills=profile.requirements.soft_skills_required
                    + profile.requirements.soft_skills_optional,
                    company_culture=profile.company.culture or "",
                    audience=audience,
                    lang=st.session_state.lang,
                    tone=st.session_state.get("tone"),
                    num_questions=selected_num,
                )
                st.session_state[StateKeys.INTERVIEW_GUIDE_MD] = guide_md
            except Exception as e:
                st.error(
                    tr(
                        "Interviewleitfaden-Generierung fehlgeschlagen: {error}. Bitte erneut versuchen.",
                        "Interview guide generation failed: {error}. Please try again.",
                    ).format(error=e)
                )

    output_tabs = st.tabs(
        [
            tr("Job Ad", "Job Ad"),
            tr("Boolean String", "Boolean String"),
            tr("Interview Guide", "Interview Guide"),
        ]
    )
    with output_tabs[0]:
        if st.session_state.get(StateKeys.JOB_AD_MD):
            st.markdown("**Job Ad Draft:**")
            st.markdown(st.session_state[StateKeys.JOB_AD_MD])
            findings = st.session_state.get(StateKeys.BIAS_FINDINGS, [])
            for f in findings:
                st.warning(
                    tr(
                        f"⚠️ Begriff '{f['term']}' erkannt. Vorschlag: {f['suggestion']}",
                        f"⚠️ Term '{f['term']}' detected. Suggestion: {f['suggestion']}",
                    )
                )
            feedback = st.text_area(
                tr("Feedback zur Anzeige", "Ad refinement feedback"),
                key=UIKeys.JOB_AD_FEEDBACK,
            )
            if st.button(
                tr("🔄 Stellenanzeige verfeinern", "🔄 Refine Job Ad"),
                key=UIKeys.REFINE_JOB_AD,
            ):
                try:
                    refined = refine_document(
                        st.session_state[StateKeys.JOB_AD_MD], feedback
                    )
                    st.session_state[StateKeys.JOB_AD_MD] = refined
                    findings = scan_bias_language(refined, st.session_state.lang)
                    st.session_state[StateKeys.BIAS_FINDINGS] = findings
                    st.rerun()
                except Exception as e:
                    st.error(
                        tr(
                            "Verfeinerung fehlgeschlagen",
                            "Refinement failed",
                        )
                        + f": {e}"
                    )
    with output_tabs[1]:
        if st.session_state.get(StateKeys.BOOLEAN_STR):
            st.write(tr("**Boolean Search String:**", "**Boolean Search String:**"))
            st.code(st.session_state[StateKeys.BOOLEAN_STR])
    with output_tabs[2]:
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
                done = set(
                    st.session_state[StateKeys.PROFILE]
                    .get("meta", {})
                    .get("followups_answered", [])
                )
                st.session_state[StateKeys.FOLLOWUPS] = [
                    q for q in res.get("questions", []) if q.get("field") not in done
                ]
                st.success(
                    tr("Follow-ups aktualisiert.", "Follow-up questions updated.")
                )
            except Exception as e:
                display_error(
                    tr("Follow-ups fehlgeschlagen", "Follow-ups failed"),
                    str(e),
                )

    with col2:
        if st.session_state.get(StateKeys.FOLLOWUPS):
            st.write(tr("**Vorgeschlagene Fragen:**", "**Suggested questions:**"))
            for item in st.session_state[StateKeys.FOLLOWUPS]:
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


# --- Haupt-Wizard-Runner ---
def run_wizard():
    """Run the multi-step profile creation wizard.

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

    steps = [
        (tr("Onboarding", "Onboarding"), lambda: _step_onboarding(schema)),
        (tr("Übersicht", "Overview"), lambda: _step_overview(schema, critical)),
        (tr("Unternehmen", "Company"), _step_company),
        (tr("Basisdaten", "Basic info"), _step_position),
        (tr("Anforderungen", "Requirements"), _step_requirements),
        (tr("Beschäftigung", "Employment"), _step_employment),
        (tr("Leistungen & Benefits", "Rewards & Benefits"), _step_compensation),
        (tr("Prozess", "Process"), _step_process),
        (tr("Summary", "Summary"), lambda: _step_summary(schema, critical)),
    ]

    # Headline
    st.markdown("### 🧭 Wizard")

    # Step Navigation (oben)
    render_stepper(st.session_state[StateKeys.STEP], [label for label, _ in steps])

    # Render current step
    current = st.session_state[StateKeys.STEP]
    _label, renderer = steps[current]
    renderer()

    # Bottom nav
    section = current - 1
    missing = get_missing_critical_fields(max_section=section) if section >= 1 else []

    if current == 0:
        _, col_next, _ = st.columns([1, 1, 1])
        with col_next:
            if current < len(steps) - 1 and st.button(
                tr("Weiter ▶︎", "Next ▶︎"),
                type="primary",
                use_container_width=True,
                disabled=bool(missing),
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
                    disabled=bool(missing),
                ):
                    next_step()
                    st.rerun()
            else:
                if st.button(
                    tr("Fertig", "Done"),
                    type="primary",
                    use_container_width=True,
                    disabled=bool(missing),
                ):
                    st.session_state[StateKeys.STEP] = 0
                    st.rerun()
