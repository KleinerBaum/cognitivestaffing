# wizard.py — Cognitive Needs Wizard (clean flow, schema-aligned)
from __future__ import annotations

import hashlib
import io
import json
import textwrap
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List, Literal, Mapping, Optional, Sequence, TypedDict
from urllib.parse import urljoin, urlparse

import re
import streamlit as st
from streamlit_sortables import sort_items

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
    summarize_company_page,
)
from core.suggestions import get_benefit_suggestions, get_skill_suggestions
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from integrations.esco import search_occupation, enrich_skills
from components.stepper import render_stepper
from components.salary_dashboard import render_salary_insights
from utils import build_boolean_search, seo_optimize
from utils.export import prepare_download_data
from nlp.bias import scan_bias_language
from core.esco_utils import normalize_skills
from core.job_ad import (
    JOB_AD_FIELDS,
    JOB_AD_GROUP_LABELS,
    iter_field_keys,
    suggest_target_audiences,
)

ROOT = Path(__file__).parent
ensure_state()

WIZARD_TITLE = (
    "Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool"
)

# Index of the first data entry step ("Unternehmen" / "Company")
COMPANY_STEP_INDEX = 1

REQUIRED_SUFFIX = " :red[*]"
REQUIRED_PREFIX = ":red[*] "

SKILL_SORTABLE_STYLE = """
.sortable-component {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
}
.sortable-container {
    flex: 1 1 220px;
    min-width: 220px;
    min-height: 180px;
    background: var(--background-secondary-color, #f6f6f9);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 0.75rem;
    padding: 0.75rem;
}
.sortable-container-header {
    font-weight: 600;
    margin-bottom: 0.4rem;
    font-size: 0.9rem;
}
.sortable-item {
    background: var(--background-color, #ffffff);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 0.5rem;
    padding: 0.4rem 0.6rem;
    margin-bottom: 0.35rem;
    font-size: 0.9rem;
}
"""

WIZARD_LAYOUT_STYLE = """
<style>
section.main > div.block-container {
    max-width: 1100px;
}
section.main > div.block-container [data-testid="stTextInput"],
section.main > div.block-container [data-testid="stNumberInput"],
section.main > div.block-container [data-testid="stDateInput"],
section.main > div.block-container [data-testid="stSelectbox"] {
    max-width: 460px;
}
section.main > div.block-container [data-testid="stTextInput"] input,
section.main > div.block-container [data-testid="stNumberInput"] input,
section.main > div.block-container [data-testid="stDateInput"] input {
    width: 100%;
}
section.main > div.block-container [data-testid="stTextArea"] textarea {
    min-height: 140px;
}
</style>
"""

FONT_CHOICES = ["Helvetica", "Arial", "Times New Roman", "Georgia", "Calibri"]

CEFR_LANGUAGE_LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2", "Native"]

GERMAN_STATES = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen",
]

EUROPEAN_COUNTRIES = [
    "Albania",
    "Andorra",
    "Austria",
    "Belarus",
    "Belgium",
    "Bosnia and Herzegovina",
    "Bulgaria",
    "Croatia",
    "Cyprus",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "Ireland",
    "Italy",
    "Kosovo",
    "Latvia",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Moldova",
    "Monaco",
    "Montenegro",
    "Netherlands",
    "North Macedonia",
    "Norway",
    "Poland",
    "Portugal",
    "Romania",
    "San Marino",
    "Serbia",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
    "Switzerland",
    "Ukraine",
    "United Kingdom",
    "Vatican City",
]

CONTINENT_COUNTRIES = {
    "Africa": [
        "Algeria",
        "Angola",
        "Egypt",
        "Ethiopia",
        "Ghana",
        "Kenya",
        "Morocco",
        "Nigeria",
        "South Africa",
        "Tanzania",
        "Tunisia",
        "Uganda",
    ],
    "Asia": [
        "China",
        "India",
        "Indonesia",
        "Japan",
        "Malaysia",
        "Philippines",
        "Singapore",
        "South Korea",
        "Thailand",
        "Vietnam",
    ],
    "Europe": EUROPEAN_COUNTRIES,
    "North America": [
        "Canada",
        "Mexico",
        "United States",
    ],
    "South America": [
        "Argentina",
        "Brazil",
        "Chile",
        "Colombia",
        "Peru",
    ],
    "Oceania": [
        "Australia",
        "Fiji",
        "New Zealand",
        "Papua New Guinea",
    ],
    "Middle East": [
        "Bahrain",
        "Israel",
        "Jordan",
        "Kuwait",
        "Oman",
        "Qatar",
        "Saudi Arabia",
        "United Arab Emirates",
    ],
}


class _CompanySectionConfig(TypedDict):
    """Configuration for a company research button."""

    key: str
    button: str
    label: str
    slugs: Sequence[str]


def _normalise_company_base_url(url: str) -> str | None:
    """Return the normalised base URL for the company website."""

    candidate = (url or "").strip()
    if not candidate:
        return None
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return None
    if parsed.path and not parsed.path.endswith("/"):
        last_segment = parsed.path.split("/")[-1]
        if "." not in last_segment:
            candidate = f"{candidate}/"
    base = urljoin(candidate, "./")
    if not base.endswith("/"):
        base = f"{base}/"
    return base


def _candidate_company_page_urls(base_url: str, slugs: Sequence[str]) -> list[str]:
    """Return a list of candidate URLs for company sub-pages."""

    urls: list[str] = []
    seen: set[str] = set()
    for slug in slugs:
        if not slug:
            continue
        trimmed = slug.strip()
        if not trimmed:
            continue
        if re.match(r"^https?://", trimmed, re.IGNORECASE):
            candidate = trimmed
        else:
            candidate = urljoin(base_url, trimmed.lstrip("/"))
        if candidate in seen:
            continue
        seen.add(candidate)
        urls.append(candidate)
    return urls


def _fetch_company_page(base_url: str, slugs: Sequence[str]) -> tuple[str, str] | None:
    """Fetch the first available company sub-page from ``slugs``."""

    for candidate in _candidate_company_page_urls(base_url, slugs):
        try:
            text = extract_text_from_url(candidate)
        except ValueError:
            continue
        content = text.strip()
        if content:
            return candidate, content
    return None


def _sync_company_page_base(base_url: str | None) -> None:
    """Reset cached summaries when the company base URL changes."""

    storage: dict[str, dict[str, str]] = st.session_state[
        StateKeys.COMPANY_PAGE_SUMMARIES
    ]
    previous = st.session_state.get(StateKeys.COMPANY_PAGE_BASE, "")
    current = base_url or ""
    if current != previous:
        st.session_state[StateKeys.COMPANY_PAGE_BASE] = current
        storage.clear()


def _load_company_page_section(
    section_key: str,
    base_url: str,
    slugs: Sequence[str],
    label: str,
) -> None:
    """Fetch and summarise a company section and store it in session state."""

    lang = st.session_state.get("lang", "de")
    with st.spinner(
        tr("Suche nach {section} …", "Fetching {section} …").format(section=label)
    ):
        result = _fetch_company_page(base_url, slugs)
    if not result:
        st.info(
            tr(
                "Keine passende Seite für '{section}' gefunden.",
                "Could not find a matching page for '{section}'.",
            ).format(section=label)
        )
        return
    url, text = result
    try:
        summary = summarize_company_page(text, label, lang=lang)
    except Exception:
        summary = textwrap.shorten(text, width=420, placeholder="…")
        st.warning(
            tr(
                "KI-Zusammenfassung fehlgeschlagen – gekürzter Auszug angezeigt.",
                "AI summary failed – showing a shortened excerpt instead.",
            )
        )
    summaries: dict[str, dict[str, str]] = st.session_state[
        StateKeys.COMPANY_PAGE_SUMMARIES
    ]
    summaries[section_key] = {"url": url, "summary": summary}
    st.success(tr("Zusammenfassung aktualisiert.", "Summary updated."))


def _render_company_research_tools(base_url: str) -> None:
    """Render buttons to analyse additional company web pages."""

    st.markdown(tr("#### 🔍 Automatische Recherche", "#### 🔍 Automatic research"))
    st.caption(
        tr(
            "Nutze die Buttons, um wichtige Unterseiten zu analysieren und kompakte Zusammenfassungen zu erhalten.",
            "Use the buttons to analyse key subpages and receive concise summaries.",
        )
    )
    normalised = _normalise_company_base_url(base_url)
    _sync_company_page_base(normalised)
    if not base_url or not base_url.strip():
        st.info(
            tr(
                "Bitte gib eine gültige Website ein, um weitere Seiten zu durchsuchen.",
                "Please provide a valid website to explore additional pages.",
            )
        )
        return
    if not normalised:
        st.warning(
            tr(
                "Die angegebene Website ist ungültig (z. B. fehlt https://).",
                "The provided website seems invalid (e.g. missing https://).",
            )
        )
        return

    display_url = normalised.rstrip("/")
    st.caption(
        tr("Erkannte Website: {url}", "Detected website: {url}").format(
            url=f"[{display_url}]({display_url})"
        )
    )

    sections: list[_CompanySectionConfig] = [
        {
            "key": "about",
            "button": tr("Über-uns-Seite analysieren", "Analyse About page"),
            "label": tr("Über uns", "About the company"),
            "slugs": [
                "unternehmen",
                "ueber-uns",
                "ueberuns",
                "about-us",
                "about",
                "company",
            ],
        },
        {
            "key": "imprint",
            "button": tr("Impressum prüfen", "Analyse imprint"),
            "label": tr("Impressum", "Imprint"),
            "slugs": [
                "impressum",
                "imprint",
                "legal",
                "legal-notice",
                "kontakt/impressum",
            ],
        },
        {
            "key": "press",
            "button": tr("Pressebereich analysieren", "Analyse press page"),
            "label": tr("Presse", "Press"),
            "slugs": [
                "presse",
                "press",
                "newsroom",
                "news",
            ],
        },
    ]

    cols = st.columns(len(sections))
    for col, section in zip(cols, sections):
        button_label = section["button"]
        section_key = section["key"]
        if col.button(button_label, key=f"ui.company.page.{section_key}"):
            _load_company_page_section(
                section_key=section_key,
                base_url=normalised,
                slugs=section["slugs"],
                label=section["label"],
            )

    summaries = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]
    for section in sections:
        section_key = section["key"]
        result = summaries.get(section_key)
        if not result:
            continue
        st.markdown(f"**{section['label']}** – [{result['url']}]({result['url']})")
        st.write(result.get("summary") or "")


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
    raw_profile = profile.model_dump()
    st.session_state[StateKeys.PROFILE] = raw_profile
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = raw_profile
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
    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": _unique_normalized(
            raw_profile.get("requirements", {}).get("hard_skills_required", [])
        ),
        "nice": _unique_normalized(
            raw_profile.get("requirements", {}).get("hard_skills_optional", [])
        ),
    }
    title = profile.position.job_title or ""
    occ = search_occupation(title, st.session_state.lang or "en") if title else None
    st.session_state[StateKeys.ESCO_SKILLS] = []
    if occ:
        profile.position.occupation_label = occ.get("preferredLabel") or ""
        profile.position.occupation_uri = occ.get("uri") or ""
        profile.position.occupation_group = occ.get("group") or ""
        skills = enrich_skills(occ.get("uri") or "", st.session_state.lang or "en")
        current_list = profile.requirements.hard_skills_required or []
        skills_clean = _unique_normalized(skills or [])
        original_markers = {item.casefold() for item in current_list}
        esco_only = [
            item for item in skills_clean if item.casefold() not in original_markers
        ]
        st.session_state[StateKeys.ESCO_SKILLS] = esco_only
        merged = _unique_normalized(current_list + skills_clean)
        profile.requirements.hard_skills_required = sorted(
            merged, key=lambda item: item.casefold()
        )
    data = profile.model_dump()
    st.session_state[StateKeys.PROFILE] = data
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

    raw_input = st.session_state.get(StateKeys.RAW_TEXT, "")
    if not raw_input:
        raw_input = st.session_state.get("__prefill_profile_text__", "")
    raw_input = raw_input or ""
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
        st.rerun()
        return

    st.session_state["_analyze_attempted"] = True
    st.session_state[StateKeys.RAW_TEXT] = raw_clean
    st.session_state["__last_extracted_hash__"] = digest
    _autodetect_lang(raw_clean)
    try:
        _extract_and_summarize(raw_clean, schema)
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
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {}
    st.session_state[StateKeys.ESCO_SKILLS] = []
    st.session_state[StateKeys.SKILL_BUCKETS] = {"must": [], "nice": []}
    st.session_state.pop("_analyze_attempted", None)
    st.session_state.pop("__last_extracted_hash__", None)
    st.session_state[StateKeys.STEP] = COMPANY_STEP_INDEX
    st.rerun()


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


def _humanize_fragment(fragment: str) -> str:
    """Return a human readable label for nested fragments."""

    cleaned = fragment.replace("_", " ").replace(".", " ")
    return cleaned.strip().title() if cleaned else fragment


def _render_preview_value(value: Any) -> None:
    """Display detected values in a compact, readable format."""

    if isinstance(value, list):
        items = [str(item) for item in value if _has_value(item)]
        if items:
            st.markdown("\n".join(f"- {item}" for item in items))
        else:
            st.caption(tr("Keine Angaben", "No entries"))
        return

    if isinstance(value, dict):
        lines: list[str] = []
        for key, val in value.items():
            if not _has_value(val):
                continue
            if isinstance(val, list):
                formatted = ", ".join(str(item) for item in val if _has_value(item))
            else:
                formatted = val
            lines.append(f"- **{_humanize_fragment(key)}:** {formatted}")
        if lines:
            st.markdown("\n".join(lines))
        else:
            st.caption(tr("Keine Angaben", "No entries"))
        return

    st.write(value)


def _render_prefilled_preview(
    *,
    include_prefixes: Sequence[str] | None = None,
    exclude_prefixes: Sequence[str] = (),
    layout: Literal["tabs", "grid"] = "tabs",
) -> None:
    """Render tabs with all fields that already contain values."""

    raw_profile = (
        st.session_state.get(StateKeys.EXTRACTION_RAW_PROFILE)
        or st.session_state.get(StateKeys.PROFILE)
        or {}
    )
    flat = flatten(raw_profile)

    def _allowed(path: str) -> bool:
        if path.startswith("meta."):
            return False
        if include_prefixes and not any(
            path.startswith(pref) for pref in include_prefixes
        ):
            return False
        if any(path.startswith(pref) for pref in exclude_prefixes):
            return False
        return _has_value(flat[path])

    filled = {path: value for path, value in flat.items() if _allowed(path)}
    if not filled:
        return

    sections: list[tuple[str, tuple[str, ...]]] = [
        (tr("Unternehmen", "Company"), ("company.",)),
        (
            tr("Basisdaten", "Basic info"),
            ("position.", "location.", "responsibilities."),
        ),
        (tr("Anforderungen", "Requirements"), ("requirements.",)),
        (tr("Beschäftigung", "Employment"), ("employment.",)),
        (
            tr("Leistungen & Benefits", "Rewards & Benefits"),
            ("compensation.",),
        ),
        (tr("Prozess", "Process"), ("process.",)),
    ]

    section_entries: list[tuple[str, list[tuple[str, Any]]]] = []
    for label, prefixes in sections:
        if include_prefixes and not any(
            any(pref.startswith(prefix) for prefix in prefixes)
            for pref in include_prefixes
        ):
            continue
        entries = [
            (path, filled[path])
            for path in sorted(filled)
            if any(path.startswith(prefix) for prefix in prefixes)
        ]
        if entries:
            section_entries.append((label, entries))

    if not section_entries:
        return

    st.markdown(
        tr(
            "#### Automatisch erkannte Informationen",
            "#### Automatically detected information",
        )
    )
    st.caption(
        tr(
            "Alle Felder lassen sich später weiterhin bearbeiten.",
            "You can still adjust every field later on.",
        )
    )

    if layout == "grid":
        cards: list[tuple[str, Any]] = [
            (path, value) for _, entries in section_entries for path, value in entries
        ]
        for start in range(0, len(cards), 2):
            row = cards[start : start + 2]
            cols = st.columns(len(row), gap="large")
            for col, (path, value) in zip(cols, row):
                with col.container(border=True):
                    st.markdown(f"**{_field_label(path)}**")
                    _render_preview_value(value)
        return

    tabs = st.tabs([label for label, _ in section_entries])
    for tab, (_, entries) in zip(tabs, section_entries):
        with tab:
            for path, value in entries:
                col_label, col_value = st.columns([1, 2], vertical_alignment="top")
                with col_label:
                    st.markdown(f"**{_field_label(path)}**")
                with col_value:
                    _render_preview_value(value)
                st.markdown(
                    "<div style='margin-bottom:0.6rem'></div>", unsafe_allow_html=True
                )


def _ensure_skill_suggestions(
    job_title: str, lang: str
) -> tuple[dict[str, list[str]], str | None]:
    """Load skill suggestions for ``job_title`` into session state if needed."""

    if not job_title:
        return {}, None
    stored = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})
    if stored.get("_title") == job_title and stored.get("_lang") == lang:
        suggestions = {
            key: stored.get(key, [])
            for key in ("hard_skills", "soft_skills", "tools_and_technologies")
        }
        return suggestions, None
    suggestions, error = get_skill_suggestions(job_title, lang=lang)
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {
        "_title": job_title,
        "_lang": lang,
        **suggestions,
    }
    if error and st.session_state.get("debug"):
        st.session_state["skill_suggest_error"] = error
    return suggestions, error


def _skill_marker_set(values: Iterable[str]) -> set[str]:
    """Return a casefolded set for quick membership tests."""

    markers: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned:
            markers.add(cleaned.casefold())
    return markers


def _extract_skill_values(profile: dict) -> list[str]:
    """Collect unique skill labels from the extracted profile."""

    requirements = profile.get("requirements", {}) if isinstance(profile, dict) else {}
    combined: list[str] = []
    for key in (
        "hard_skills_required",
        "hard_skills_optional",
        "tools_and_technologies",
    ):
        combined.extend(requirements.get(key, []))
    return _unique_normalized(combined)


def _render_skill_triage(raw_profile: dict) -> None:
    """Render drag & drop skill buckets for must-have and nice-to-have skills."""

    extracted_skills = _extract_skill_values(raw_profile)
    esco_skills = _unique_normalized(
        st.session_state.get(StateKeys.ESCO_SKILLS, []) or []
    )
    job_title = (raw_profile.get("position", {}).get("job_title", "") or "").strip()
    lang = st.session_state.get("lang", "en")
    if job_title:
        _ensure_skill_suggestions(job_title, lang)
    suggestions_state = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})
    llm_candidates: list[str] = []
    for key in ("hard_skills", "soft_skills", "tools_and_technologies"):
        llm_candidates.extend(suggestions_state.get(key, []))
    llm_suggestions = _unique_normalized(llm_candidates)
    extracted_markers = _skill_marker_set(extracted_skills)
    esco_markers = _skill_marker_set(esco_skills)
    llm_suggestions = [
        item
        for item in llm_suggestions
        if item.casefold() not in extracted_markers
        and item.casefold() not in esco_markers
    ][:5]

    buckets = st.session_state.get(StateKeys.SKILL_BUCKETS) or {"must": [], "nice": []}
    must_default = _unique_normalized(buckets.get("must", []))
    nice_default = _unique_normalized(buckets.get("nice", []))
    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": must_default,
        "nice": nice_default,
    }

    assigned_markers = _skill_marker_set(must_default + nice_default)
    available_extracted = [
        item for item in extracted_skills if item.casefold() not in assigned_markers
    ]
    available_esco = [
        item for item in esco_skills if item.casefold() not in assigned_markers
    ]
    available_llm = [
        item for item in llm_suggestions if item.casefold() not in assigned_markers
    ]

    if not (
        available_extracted
        or available_esco
        or available_llm
        or must_default
        or nice_default
    ):
        return

    st.markdown(tr("#### Skills priorisieren", "#### Prioritise skills"))
    st.caption(
        tr(
            "Ziehe die Skills per Drag & Drop in die passende Box.",
            "Drag each skill into the appropriate bucket.",
        )
    )

    label_extracted = tr("Extrahierte Skills", "Extracted skills")
    label_esco = tr("ESCO Vorschläge", "ESCO suggestions")
    label_llm = tr("LLM Vorschläge", "LLM suggestions")
    label_must = tr("Must-have", "Must-have")
    label_nice = tr("Nice-to-have", "Nice-to-have")

    containers = [
        {"header": label_extracted, "items": available_extracted},
        {"header": label_esco, "items": available_esco},
        {"header": label_llm, "items": available_llm},
        {"header": label_must, "items": must_default},
        {"header": label_nice, "items": nice_default},
    ]

    result = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal",
        custom_style=SKILL_SORTABLE_STYLE,
        key="skill_triage",
    )
    if not result:
        return

    container_map = {item.get("header"): item.get("items", []) for item in result}
    must_list = _unique_normalized(container_map.get(label_must, []))
    nice_list = _unique_normalized(container_map.get(label_nice, []))
    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": must_list,
        "nice": nice_list,
    }


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


def _job_ad_get_value(data: Mapping[str, Any], key: str) -> Any:
    """Return a value for ``key`` supporting both nested and dotted lookups."""

    if isinstance(data, Mapping) and key in data:
        return data[key]
    return get_in(dict(data), key) if isinstance(data, Mapping) else None


def _normalize_list(value: Any) -> list[str]:
    """Normalise raw list or string inputs into a clean list of strings."""

    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    return []


def _job_ad_field_value(data: Mapping[str, Any], key: str, lang: str) -> str:
    """Format a field value for display within the job-ad selection UI."""

    is_de = lang.lower().startswith("de")
    yes_no = ("Ja", "Nein") if is_de else ("Yes", "No")

    if key == "compensation.salary":
        provided = bool(_job_ad_get_value(data, "compensation.salary_provided"))
        if not provided:
            return ""
        min_val = _job_ad_get_value(data, "compensation.salary_min") or 0
        max_val = _job_ad_get_value(data, "compensation.salary_max") or 0
        currency = _job_ad_get_value(data, "compensation.currency") or "EUR"
        period = _job_ad_get_value(data, "compensation.period") or (
            "Jahr" if is_de else "year"
        )
        try:
            min_num = int(min_val)
            max_num = int(max_val)
        except (TypeError, ValueError):
            return ""
        if not min_num and not max_num:
            return ""
        if min_num and max_num:
            return f"{min_num:,}–{max_num:,} {currency} / {period}"
        amount = max_num or min_num
        return f"{amount:,} {currency} / {period}"

    raw = _job_ad_get_value(data, key)
    if raw in (None, "", []):
        return ""

    if key == "employment.travel_required":
        detail = _job_ad_get_value(data, "employment.travel_details")
        if detail:
            raw = detail
        else:
            raw = bool(raw)
    elif key == "employment.relocation_support":
        detail = _job_ad_get_value(data, "employment.relocation_details")
        if detail:
            raw = detail
        else:
            raw = bool(raw)
    elif key == "employment.work_policy":
        details_text = _job_ad_get_value(data, "employment.work_policy_details")
        if not details_text:
            percentage = _job_ad_get_value(data, "employment.remote_percentage")
            if percentage:
                details_text = (
                    f"{percentage}% Home-Office" if is_de else f"{percentage}% remote"
                )
        if details_text and isinstance(raw, str):
            return f"{raw.strip()} ({details_text})"
    elif key == "employment.remote_percentage":
        return f"{raw}% Home-Office" if is_de else f"{raw}% remote"

    if isinstance(raw, bool):
        return yes_no[0] if raw else yes_no[1]
    if isinstance(raw, list):
        items = _normalize_list(raw)
        if key == "compensation.benefits":
            deduped: list[str] = []
            seen: set[str] = set()
            for entry in items:
                lowered = entry.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    deduped.append(entry)
            items = deduped
        return ", ".join(items)
    if isinstance(raw, str):
        return raw.strip()
    return str(raw)


def _job_ad_field_display(
    data: Mapping[str, Any],
    field_key: str,
    lang: str,
) -> tuple[str, str] | None:
    """Return the translated label and formatted value for ``field_key``."""

    value = _job_ad_field_value(data, field_key, lang)
    if not value:
        return None
    is_de = lang.lower().startswith("de")
    label = next(
        (
            field.label_de if is_de else field.label_en
            for field in JOB_AD_FIELDS
            if field.key == field_key
        ),
        field_key,
    )
    return label, value


def _set_job_ad_field(field_key: str, enabled: bool) -> None:
    """Update the selected job-ad fields set."""

    current = set(st.session_state.get(StateKeys.JOB_AD_SELECTED_FIELDS, set()))
    if enabled:
        current.add(field_key)
    else:
        current.discard(field_key)
    st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = current


def _toggle_job_ad_field(field_key: str, widget_key: str) -> None:
    """Sync checkbox widgets with the stored job-ad field selection."""

    checked = bool(st.session_state.get(widget_key))
    _set_job_ad_field(field_key, checked)


def _update_job_ad_font() -> None:
    """Persist the selected export font in session state."""

    selected = st.session_state.get(UIKeys.JOB_AD_FONT)
    if selected:
        st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = selected


def _job_ad_style_reference(data: Mapping[str, Any], base_url: str | None) -> str:
    """Compose a short style reference string for the job ad prompt."""

    parts: list[str] = []
    brand_keywords = _job_ad_get_value(data, "company.brand_keywords")
    if brand_keywords:
        parts.append(str(brand_keywords))
    mission = _job_ad_get_value(data, "company.mission")
    if mission:
        parts.append(str(mission))
    if base_url:
        parts.append(base_url)
    return " | ".join(parts)


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


def _apply_skill_buckets_to_profile() -> None:
    """Persist the drag-and-drop skill buckets into the profile."""

    buckets = st.session_state.get(StateKeys.SKILL_BUCKETS, {}) or {}
    must = _unique_normalized(buckets.get("must", []))
    nice = _unique_normalized(buckets.get("nice", []))
    st.session_state[StateKeys.SKILL_BUCKETS] = {"must": must, "nice": nice}
    _update_profile("requirements.hard_skills_required", must)
    _update_profile("requirements.hard_skills_optional", nice)


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
    """Render onboarding with language toggle, intro, and ingestion options."""

    _maybe_run_extraction(schema)

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    welcome_headline = tr(
        "Willkommen zum Onboarding",
        "Welcome to onboarding",
    )
    welcome_text = tr(
        "Wir freuen uns, dich zu begleiten.",
        "We are excited to guide you through the process.",
    )
    advantage_text = tr(
        (
            "Mache den ersten Schritt jedes Recruiting-Prozesses mit einer "
            "kompletten Sammlung an Informationen, die im Verlauf wichtig "
            "werden könnten, und spare viel Geld, Zeit und Mühe – so legst du "
            "die Basis für eine langfristig funktionierende Kooperation."
        ),
        (
            "Take the first step of every recruiting process with a complete "
            "collection of information that might become important later on "
            "and save money, time, and effort – creating the foundation for a "
            "long-term collaboration that works."
        ),
    )
    dynamic_text = tr(
        (
            "Auf Basis deiner Stellenbeschreibung passen wir den Fragenprozess "
            "dynamisch an und reduzieren so Schreibarbeit auf das Nötigste."
        ),
        (
            "Based on your job description we dynamically adapt the question "
            "flow so that you only need to provide the essentials."
        ),
    )

    st.markdown(
        f"<div style='text-align:center; margin-top: 1.5rem;'>"
        f"<h2>{welcome_headline}</h2>"
        f"<p>{welcome_text}</p>"
        f"<p>{advantage_text}</p>"
        f"<p>{dynamic_text}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    method_options = [
        ("text", tr("Text eingeben", "Enter text")),
        ("file", tr("Datei hochladen", "Upload file")),
        ("url", tr("URL eingeben", "Enter URL")),
    ]
    method_labels = {value: label for value, label in method_options}
    if UIKeys.INPUT_METHOD not in st.session_state:
        st.session_state[UIKeys.INPUT_METHOD] = "text"

    st.divider()
    st.subheader(tr("Wie möchtest du starten?", "How would you like to begin?"))
    st.caption(
        tr(
            "Du kannst jederzeit zwischen den Eingabemethoden wechseln. Die Analyse startet automatisch, sobald Inhalte vorliegen.",
            "Feel free to switch methods at any time. Analysis starts automatically as soon as content is available.",
        )
    )

    st.radio(
        tr("Eingabemethode", "Input method"),
        options=list(method_labels.keys()),
        key=UIKeys.INPUT_METHOD,
        format_func=method_labels.__getitem__,
        horizontal=True,
    )

    if st.session_state.pop("source_error", False):
        st.info(
            tr(
                "Es gab ein Problem beim Import. Du kannst die Angaben auch manuell ergänzen.",
                "There was an issue while importing the content. You can still fill in the details manually.",
            )
        )

    prefill = st.session_state.pop("__prefill_profile_text__", None)
    if prefill is not None:
        st.session_state[UIKeys.PROFILE_TEXT_INPUT] = prefill
        st.session_state[StateKeys.RAW_TEXT] = prefill

    def _queue_extraction_if_ready() -> None:
        raw_text = st.session_state.get(StateKeys.RAW_TEXT, "")
        if raw_text and raw_text.strip():
            st.session_state["__run_extraction__"] = True

    method = st.session_state[UIKeys.INPUT_METHOD]
    if method == "text":
        bind_textarea(
            tr("Jobtext", "Job text"),
            UIKeys.PROFILE_TEXT_INPUT,
            StateKeys.RAW_TEXT,
            placeholder=tr(
                "Füge hier den Text deiner Stellenanzeige ein …",
                "Paste the text of your job posting here …",
            ),
            help=tr(
                "Wir analysieren den Text automatisch und befüllen alle passenden Felder.",
                "We automatically analyse the text and prefill all relevant fields.",
            ),
            on_change=_queue_extraction_if_ready,
        )
        st.caption(
            tr(
                "Sobald du Text ergänzt oder änderst, startet die Analyse ohne weiteren Klick.",
                "As soon as you add or change the text, the analysis starts automatically.",
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
                "Direkt nach dem Upload beginnen wir mit der Analyse.",
                "We start analysing immediately after the upload finishes.",
            ),
        )
    else:
        st.text_input(
            tr("Öffentliche Stellenanzeigen-URL", "Public job posting URL"),
            key=UIKeys.PROFILE_URL_INPUT,
            on_change=on_url_changed,
            placeholder="https://example.com/job",
            help=tr(
                "Die URL muss ohne Login erreichbar sein. Wir übernehmen den Inhalt automatisch.",
                "The URL needs to be accessible without authentication. We will fetch the content automatically.",
            ),
        )

    _render_prefilled_preview(exclude_prefixes=("requirements.",))

    col_skip, col_next = st.columns(2)
    with col_skip:
        if st.button(
            tr("Ohne Vorlage fortfahren", "Continue without template"),
            type="secondary",
            use_container_width=True,
        ):
            _skip_source()

    with col_next:
        if st.button(
            tr("Weiter", "Next"),
            type="primary",
            use_container_width=True,
        ):
            st.session_state[StateKeys.STEP] = COMPANY_STEP_INDEX
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

        _render_company_research_tools(data["company"].get("website", ""))

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


def _filter_existing_participants(
    participants: Sequence[str],
    stakeholder_names: Sequence[str],
) -> list[str]:
    """Return participants that still exist in ``stakeholder_names``.

    Args:
        participants: The participants saved for a phase.
        stakeholder_names: Current list of available stakeholder names.

    Returns:
        Filtered list containing only participants still available for selection.
    """

    existing = {name for name in stakeholder_names if name}
    return [participant for participant in participants if participant in existing]


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
            phase_participants = _filter_existing_participants(
                phase.get("participants", []), stakeholder_names
            )
            phase["participants"] = st.multiselect(
                tr("Beteiligte", "Participants"),
                stakeholder_names,
                default=phase_participants,
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
    raw_profile = (
        st.session_state.get(StateKeys.EXTRACTION_RAW_PROFILE)
        or st.session_state.get(StateKeys.PROFILE)
        or {}
    )
    _render_prefilled_preview(
        include_prefixes=("requirements.",),
        layout="grid",
    )
    _render_skill_triage(raw_profile)
    _apply_skill_buckets_to_profile()
    data = st.session_state[StateKeys.PROFILE]
    missing_here = [
        f
        for f in get_missing_critical_fields(max_section=3)
        if FIELD_SECTION_MAP.get(f) == 3
    ]

    # LLM-basierte Skill-Vorschläge abrufen
    job_title = (data.get("position", {}).get("job_title", "") or "").strip()
    suggestions: dict[str, list[str]] = {}
    if job_title:
        suggestions, err = _ensure_skill_suggestions(
            job_title, st.session_state.get("lang", "en")
        )
        if err or not any(suggestions.values()):
            st.warning(
                tr(
                    "Skill-Vorschläge nicht verfügbar (API-Fehler)",
                    "Skill suggestions not available (API error)",
                )
            )
    suggestions = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})

    label_hard_req = tr("Hard Skills (Muss)", "Hard Skills (Must-have)")
    if "requirements.hard_skills_required" in missing_here:
        label_hard_req += REQUIRED_SUFFIX
    col_hard_req, col_hard_opt = st.columns(2, gap="large")
    with col_hard_req:
        data["requirements"]["hard_skills_required"] = _chip_multiselect(
            label_hard_req,
            options=data["requirements"].get("hard_skills_required", []),
            values=data["requirements"].get("hard_skills_required", []),
        )
        if "requirements.hard_skills_required" in missing_here and not data[
            "requirements"
        ].get("hard_skills_required"):
            st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))
    with col_hard_opt:
        data["requirements"]["hard_skills_optional"] = _chip_multiselect(
            tr("Hard Skills (Nice-to-have)", "Hard Skills (Nice-to-have)"),
            options=data["requirements"].get("hard_skills_optional", []),
            values=data["requirements"].get("hard_skills_optional", []),
        )

    label_soft_req = tr("Soft Skills (Muss)", "Soft Skills (Must-have)")
    if "requirements.soft_skills_required" in missing_here:
        label_soft_req += REQUIRED_SUFFIX
    col_soft_req, col_soft_opt = st.columns(2, gap="large")
    with col_soft_req:
        data["requirements"]["soft_skills_required"] = _chip_multiselect(
            label_soft_req,
            options=data["requirements"].get("soft_skills_required", []),
            values=data["requirements"].get("soft_skills_required", []),
        )
        if "requirements.soft_skills_required" in missing_here and not data[
            "requirements"
        ].get("soft_skills_required"):
            st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))
    with col_soft_opt:
        data["requirements"]["soft_skills_optional"] = _chip_multiselect(
            tr("Soft Skills (Nice-to-have)", "Soft Skills (Nice-to-have)"),
            options=data["requirements"].get("soft_skills_optional", []),
            values=data["requirements"].get("soft_skills_optional", []),
        )

    col_tools, col_certs = st.columns(2, gap="large")
    with col_tools:
        data["requirements"]["tools_and_technologies"] = _chip_multiselect(
            tr("Tools & Tech", "Tools & Tech"),
            options=data["requirements"].get("tools_and_technologies", []),
            values=data["requirements"].get("tools_and_technologies", []),
        )
    with col_certs:
        data["requirements"]["certifications"] = _chip_multiselect(
            tr("Zertifizierungen", "Certifications"),
            options=data["requirements"].get("certifications", []),
            values=data["requirements"].get("certifications", []),
        )

    col_lang_req, col_lang_opt = st.columns(2, gap="large")
    with col_lang_req:
        data["requirements"]["languages_required"] = _chip_multiselect(
            tr("Sprachen", "Languages"),
            options=data["requirements"].get("languages_required", []),
            values=data["requirements"].get("languages_required", []),
        )
    with col_lang_opt:
        data["requirements"]["languages_optional"] = _chip_multiselect(
            tr("Optionale Sprachen", "Optional languages"),
            options=data["requirements"].get("languages_optional", []),
            values=data["requirements"].get("languages_optional", []),
        )

    current_language_level = data["requirements"].get("language_level_english") or ""
    language_level_options = list(CEFR_LANGUAGE_LEVELS)
    if current_language_level and current_language_level not in language_level_options:
        language_level_options.append(current_language_level)
    col_level, _ = st.columns([1, 1], gap="large")
    with col_level:
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

    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": _unique_normalized(
            data["requirements"].get("hard_skills_required", [])
        ),
        "nice": _unique_normalized(
            data["requirements"].get("hard_skills_optional", [])
        ),
    }

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
        col_share, col_region, col_details = st.columns((1, 2, 2))
        share_default = int(data["employment"].get("travel_share") or 0)
        data["employment"]["travel_share"] = col_share.number_input(
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
        current_scope = data["employment"].get("travel_region_scope", "germany")
        scope_index = next(
            (
                idx
                for idx, (value, _) in enumerate(scope_options)
                if value == current_scope
            ),
            0,
        )
        selected_scope = col_region.selectbox(
            tr("Reiseregion", "Travel region"),
            options=[value for value, _ in scope_options],
            format_func=lambda opt: scope_lookup[opt],
            index=scope_index,
        )
        data["employment"]["travel_region_scope"] = selected_scope

        stored_regions = data["employment"].get("travel_regions", [])
        stored_continents = data["employment"].get("travel_continents", [])

        if selected_scope == "germany":
            selected_regions = col_region.multiselect(
                tr("Bundesländer", "Federal states"),
                options=GERMAN_STATES,
                default=[
                    region for region in stored_regions if region in GERMAN_STATES
                ],
            )
            data["employment"]["travel_regions"] = selected_regions
            data["employment"].pop("travel_continents", None)
        elif selected_scope == "europe":
            selected_regions = col_region.multiselect(
                tr("Länder (Europa)", "Countries (Europe)"),
                options=EUROPEAN_COUNTRIES,
                default=[
                    region for region in stored_regions if region in EUROPEAN_COUNTRIES
                ],
            )
            data["employment"]["travel_regions"] = selected_regions
            data["employment"].pop("travel_continents", None)
        else:
            selected_continents = col_region.multiselect(
                tr("Kontinente", "Continents"),
                options=list(CONTINENT_COUNTRIES.keys()),
                default=[
                    continent
                    for continent in stored_continents
                    if continent in CONTINENT_COUNTRIES
                ],
            )
            data["employment"]["travel_continents"] = selected_continents
            available_countries = sorted(
                {
                    country
                    for continent in selected_continents
                    for country in CONTINENT_COUNTRIES.get(continent, [])
                }
            )
            if not available_countries:
                available_countries = sorted(
                    {
                        country
                        for countries in CONTINENT_COUNTRIES.values()
                        for country in countries
                    }
                )
            selected_countries = col_region.multiselect(
                tr("Länder", "Countries"),
                options=available_countries,
                default=[
                    region for region in stored_regions if region in available_countries
                ],
            )
            data["employment"]["travel_regions"] = selected_countries

        data["employment"]["travel_details"] = col_details.text_input(
            tr("Reisedetails", "Travel details"),
            value=data["employment"].get("travel_details", ""),
        )
    else:
        for field_name in [
            "travel_details",
            "travel_share",
            "travel_region_scope",
            "travel_regions",
            "travel_continents",
        ]:
            data["employment"].pop(field_name, None)

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

    try:
        profile = NeedAnalysisProfile.model_validate(data)
    except Exception:
        profile = NeedAnalysisProfile()

    lang = st.session_state.get("lang", "de")
    current_selection = set(
        iter_field_keys(st.session_state.get(StateKeys.JOB_AD_SELECTED_FIELDS, set()))
    )
    st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = current_selection

    if not current_selection:
        defaults: set[str] = set()
        for field in JOB_AD_FIELDS:
            display = _job_ad_field_display(data, field.key, lang)
            if display:
                defaults.add(field.key)
        current_selection = defaults
        st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = current_selection

    st.markdown(tr("### Stellenanzeige vorbereiten", "### Prepare job ad"))

    group_order: list[str] = []
    grouped_fields: dict[str, list[tuple[str, str, str]]] = {}
    for field in JOB_AD_FIELDS:
        if field.group not in group_order:
            group_order.append(field.group)
        display = _job_ad_field_display(data, field.key, lang)
        if not display:
            continue
        label, value = display
        grouped_fields.setdefault(field.group, []).append((field.key, label, value))

    for group in group_order:
        items = grouped_fields.get(group, [])
        if not items:
            continue
        label_de, label_en = JOB_AD_GROUP_LABELS.get(group, (group, group))
        group_label = label_de if lang.lower().startswith("de") else label_en
        expanded = group in {"basic", "company"}
        with st.expander(group_label, expanded=expanded):
            for key, label, value in items:
                widget_key = f"{UIKeys.JOB_AD_FIELD_PREFIX}{key}"
                desired = key in current_selection
                if (
                    widget_key not in st.session_state
                    or st.session_state[widget_key] != desired
                ):
                    st.session_state[widget_key] = desired
                st.checkbox(
                    label,
                    key=widget_key,
                    on_change=_toggle_job_ad_field,
                    kwargs={"field_key": key, "widget_key": widget_key},
                )
                st.caption(value)

    available_groups = [g for g in group_order if grouped_fields.get(g)]
    if available_groups:
        st.markdown(tr("#### Schrittweise Auswahl", "#### Step-by-step selection"))
        if UIKeys.JOB_AD_STEP_SELECT not in st.session_state:
            st.session_state[UIKeys.JOB_AD_STEP_SELECT] = available_groups[0]
        step_choice = st.selectbox(
            tr("Wizard-Schritt", "Wizard step"),
            options=available_groups,
            format_func=lambda g: (
                JOB_AD_GROUP_LABELS.get(g, (g, g))[0]
                if lang.lower().startswith("de")
                else JOB_AD_GROUP_LABELS.get(g, (g, g))[1]
            ),
            key=UIKeys.JOB_AD_STEP_SELECT,
        )
        for key, label, value in grouped_fields.get(step_choice, []):
            st.markdown(f"**{label}**")
            st.caption(value)
            is_selected = key in st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS]
            action_label = (
                tr("Aus Auswahl entfernen", "Remove from selection")
                if is_selected
                else tr("Zur Auswahl hinzufügen", "Add to selection")
            )
            button_key = f"{UIKeys.JOB_AD_STEP_FIELD_PREFIX}{key}.{int(is_selected)}"
            if st.button(action_label, key=button_key):
                _set_job_ad_field(key, not is_selected)
                st.rerun()

    st.markdown(tr("#### Manuelle Ergänzungen", "#### Manual additions"))
    manual_entries: list[dict[str, str]] = list(
        st.session_state.get(StateKeys.JOB_AD_MANUAL_ENTRIES, [])
    )
    manual_title = st.text_input(
        tr("Titel (optional)", "Title (optional)"),
        key=UIKeys.JOB_AD_MANUAL_TITLE,
    )
    manual_text = st.text_area(
        tr("Freitext", "Free text"),
        key=UIKeys.JOB_AD_MANUAL_TEXT,
    )
    if st.button(tr("➕ Eintrag hinzufügen", "➕ Add entry")):
        if manual_text.strip():
            entry = {"title": manual_title.strip(), "content": manual_text.strip()}
            manual_entries.append(entry)
            st.session_state[StateKeys.JOB_AD_MANUAL_ENTRIES] = manual_entries
            st.success(tr("Eintrag ergänzt.", "Entry added."))
        else:
            st.warning(
                tr(
                    "Bitte Text für den manuellen Eintrag angeben.",
                    "Please provide text for the manual entry.",
                )
            )

    if manual_entries:
        for idx, entry in enumerate(manual_entries):
            title = entry.get("title") or tr(
                "Zusätzliche Information", "Additional information"
            )
            st.markdown(f"**{title}**")
            st.write(entry.get("content", ""))
            if st.button(
                tr("Entfernen", "Remove"),
                key=f"{UIKeys.JOB_AD_MANUAL_TEXT}.remove.{idx}",
            ):
                manual_entries.pop(idx)
                st.session_state[StateKeys.JOB_AD_MANUAL_ENTRIES] = manual_entries
                st.rerun()

    suggestions = suggest_target_audiences(profile, lang)
    target_value = ""
    if suggestions:
        st.markdown(
            tr("#### Zielgruppen-Vorschläge", "#### Target audience suggestions")
        )
        option_map = {s.key: s for s in suggestions}
        option_keys = list(option_map.keys())
        if UIKeys.JOB_AD_TARGET_SELECT not in st.session_state or (
            st.session_state[UIKeys.JOB_AD_TARGET_SELECT] not in option_keys
        ):
            st.session_state[UIKeys.JOB_AD_TARGET_SELECT] = option_keys[0]
        selected_option = st.radio(
            tr("Empfehlungen", "Recommendations"),
            option_keys,
            format_func=lambda k: f"{option_map[k].title} – {option_map[k].description}",
            key=UIKeys.JOB_AD_TARGET_SELECT,
        )
        chosen = option_map.get(selected_option, suggestions[0])
        target_value = f"{chosen.title} – {chosen.description}"
    custom_target = st.text_input(
        tr("Eigene Zielgruppe", "Custom target audience"),
        key=UIKeys.JOB_AD_CUSTOM_TARGET,
    ).strip()
    if custom_target:
        target_value = custom_target
    st.session_state[StateKeys.JOB_AD_SELECTED_AUDIENCE] = target_value

    base_url = st.session_state.get(StateKeys.COMPANY_PAGE_BASE) or ""
    style_reference = _job_ad_style_reference(data, base_url or None)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        disabled = not current_selection or not target_value
        if st.button(
            tr("📝 Stellenanzeige generieren", "📝 Generate job ad"),
            disabled=disabled,
        ):
            try:
                job_ad_md = generate_job_ad(
                    data,
                    sorted(current_selection),
                    target_audience=target_value,
                    manual_sections=list(manual_entries),
                    style_reference=style_reference,
                    lang=lang,
                )
                st.session_state[StateKeys.JOB_AD_MD] = job_ad_md
                findings = scan_bias_language(job_ad_md, lang)
                st.session_state[StateKeys.BIAS_FINDINGS] = findings
                st.success(tr("Stellenanzeige erstellt.", "Job ad created."))
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
        job_ad_text = st.session_state.get(StateKeys.JOB_AD_MD, "")
        if job_ad_text:
            st.markdown("**Job Ad Draft:**")
            st.markdown(job_ad_text)

            st.success(
                tr(
                    "Die Anzeige wurde DSGVO-konform formuliert und SEO-optimiert. Bitte prüfe die Inhalte vor der Veröffentlichung.",
                    "The job ad has been written with GDPR compliance and SEO optimisation in mind. Please review before publishing.",
                )
            )

            seo_data = seo_optimize(job_ad_text)
            keywords: list[str] = list(seo_data.get("keywords", []))
            meta_description: str = str(seo_data.get("meta_description", ""))
            if keywords or meta_description:
                with st.expander(
                    tr("SEO-Empfehlungen", "SEO insights"), expanded=False
                ):
                    if keywords:
                        st.markdown(
                            tr("**Top-Schlüsselbegriffe:**", "**Top keywords:**")
                        )
                        st.write(", ".join(keywords))
                    if meta_description:
                        st.markdown(
                            tr("**Meta-Beschreibung:**", "**Meta description:**")
                        )
                        st.write(meta_description)

            findings = st.session_state.get(StateKeys.BIAS_FINDINGS, [])
            for finding in findings:
                st.warning(
                    tr(
                        f"⚠️ Begriff '{finding['term']}' erkannt. Vorschlag: {finding['suggestion']}",
                        f"⚠️ Term '{finding['term']}' detected. Suggestion: {finding['suggestion']}",
                    )
                )

            target_focus = st.session_state.get(StateKeys.JOB_AD_SELECTED_AUDIENCE, "")
            if target_focus:
                st.caption(
                    tr(
                        "Fokus der Anzeige: {audience}",
                        "Ad focus: {audience}",
                    ).format(audience=target_focus)
                )

            st.markdown(tr("#### Ausgabe & Branding", "#### Output & branding"))
            if style_reference:
                st.caption(
                    tr(
                        "Styleguide-Hinweise wurden automatisch aus den Unternehmensinformationen berücksichtigt.",
                        "Style guide hints were applied automatically based on the company information.",
                    )
                )
            else:
                st.caption(
                    tr(
                        "Kein Styleguide verfügbar? Wähle eine Schriftart und lade optional ein Logo hoch.",
                        "No style guide available? Choose a font and optionally upload a logo.",
                    )
                )

            format_labels = {
                "docx": tr("Word (.docx)", "Word (.docx)"),
                "pdf": tr("PDF (.pdf)", "PDF (.pdf)"),
            }
            if UIKeys.JOB_AD_FORMAT not in st.session_state:
                st.session_state[UIKeys.JOB_AD_FORMAT] = "docx"
            format_choice = st.radio(
                tr("Download-Format", "Download format"),
                list(format_labels.keys()),
                key=UIKeys.JOB_AD_FORMAT,
                format_func=lambda value: format_labels[value],
                horizontal=True,
            )

            font_default = st.session_state.get(
                StateKeys.JOB_AD_FONT_CHOICE, FONT_CHOICES[0]
            )
            if font_default not in FONT_CHOICES:
                font_default = FONT_CHOICES[0]
                st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = font_default
            font_index = FONT_CHOICES.index(font_default)
            st.selectbox(
                tr("Schriftart für Export", "Export font"),
                FONT_CHOICES,
                index=font_index,
                key=UIKeys.JOB_AD_FONT,
                on_change=_update_job_ad_font,
            )
            font_choice = st.session_state.get(
                StateKeys.JOB_AD_FONT_CHOICE, font_default
            )

            logo_file = st.file_uploader(
                tr("Logo hochladen (optional)", "Upload logo (optional)"),
                type=["png", "jpg", "jpeg", "svg"],
                key=UIKeys.JOB_AD_LOGO_UPLOAD,
            )
            if logo_file is not None:
                st.session_state[StateKeys.JOB_AD_LOGO_DATA] = logo_file.getvalue()

            logo_bytes = st.session_state.get(StateKeys.JOB_AD_LOGO_DATA)
            if logo_bytes:
                try:
                    st.image(
                        logo_bytes,
                        caption=tr("Aktuelles Logo", "Current logo"),
                        width=180,
                    )
                except Exception:
                    st.caption(
                        tr(
                            "Logo erfolgreich geladen.",
                            "Logo uploaded successfully.",
                        )
                    )
                if st.button(
                    tr("Logo entfernen", "Remove logo"),
                    key=f"{UIKeys.JOB_AD_LOGO_UPLOAD}.remove",
                ):
                    st.session_state[StateKeys.JOB_AD_LOGO_DATA] = None
                    st.rerun()

            company_name = (
                profile.company.brand_name
                or profile.company.name
                or str(_job_ad_get_value(data, "company.name") or "").strip()
                or None
            )
            job_title = (
                profile.position.job_title
                or str(_job_ad_get_value(data, "position.job_title") or "").strip()
                or "job-ad"
            )
            safe_stem = (
                re.sub(r"[^A-Za-z0-9_-]+", "-", job_title).strip("-") or "job-ad"
            )
            export_font = font_choice if format_choice in {"docx", "pdf"} else None
            export_logo = logo_bytes if format_choice in {"docx", "pdf"} else None
            payload, mime, ext = prepare_download_data(
                job_ad_text,
                format_choice,
                key="job_ad",
                title=job_title,
                font=export_font,
                logo=export_logo,
                company_name=company_name,
            )
            st.download_button(
                tr("⬇️ Als Datei herunterladen", "⬇️ Download file"),
                payload,
                file_name=f"{safe_stem}.{ext}",
                mime=mime,
                key="download_job_ad",
            )

            st.markdown(
                tr("#### Feedback & Überarbeitung", "#### Feedback & refinement")
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
                    refined = refine_document(job_ad_text, feedback)
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

    if st.session_state.get(StateKeys.FOLLOWUPS):
        st.write(tr("**Vorgeschlagene Fragen:**", "**Suggested questions:**"))
        for item in st.session_state[StateKeys.FOLLOWUPS]:
            key = item.get("key")  # dot key, z.B. "requirements.hard_skills_required"
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

    st.markdown(WIZARD_LAYOUT_STYLE, unsafe_allow_html=True)

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

    if current in {2, 3, 4, 5}:
        main_col, insight_col = st.columns((2.2, 1), gap="large")
        with main_col:
            renderer()
        with insight_col:
            render_salary_insights(st.session_state)
    else:
        renderer()

    # Bottom nav
    section = current - 1
    missing = get_missing_critical_fields(max_section=section) if section >= 1 else []

    if current > 0:
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
