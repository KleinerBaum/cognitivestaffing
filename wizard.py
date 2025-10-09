# wizard.py — Cognitive Needs Wizard (clean flow, schema-aligned)
from __future__ import annotations

import html
import hashlib
import json
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
)
from urllib.parse import urljoin, urlparse

import re
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from utils.i18n import tr
from constants.keys import UIKeys, StateKeys
from utils.session import bind_textarea
from state import ensure_state, reset_state
from ingest.extractors import extract_text_from_file, extract_text_from_url
from ingest.reader import clean_structured_document
from ingest.types import StructuredDocument, build_plain_text_document
from ingest.heuristics import apply_basic_fallbacks
from utils.errors import display_error
from utils.url_utils import is_supported_url
from config_loader import load_json
from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill
from core.confidence import ConfidenceTier, DEFAULT_AI_TIER
from core.rules import apply_rules, matches_to_patch, build_rule_metadata
from core.preview import build_prefilled_sections
from llm.client import extract_json

# LLM and Follow-ups
from openai_utils import (
    extract_company_info,
    generate_interview_guide,
    generate_job_ad,
    stream_job_ad,
    refine_document,
    summarize_company_page,
)
from core.suggestions import (
    get_benefit_suggestions,
    get_onboarding_suggestions,
    get_skill_suggestions,
    get_static_benefit_shortlist,
)
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from components.stepper import render_stepper
from utils import build_boolean_query, build_boolean_search, seo_optimize
from utils.contact import infer_contact_name_from_email
from utils.normalization import normalize_country, normalize_language_list
from utils.export import prepare_clean_json, prepare_download_data
from utils.usage import build_usage_markdown, usage_totals
from nlp.bias import scan_bias_language
from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    normalize_skills,
)
from core.job_ad import (
    JOB_AD_FIELDS,
    JOB_AD_GROUP_LABELS,
    JobAdFieldDefinition,
    resolve_job_ad_field_selection,
    suggest_target_audiences,
)

ROOT = Path(__file__).parent
ensure_state()

WIZARD_TITLE = (
    "Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool"
)

T = TypeVar("T")


class FieldLockConfig(TypedDict, total=False):
    """Configuration returned by ``_field_lock_config`` for widget rendering."""

    label: str
    help_text: str
    disabled: bool
    unlocked: bool
    was_locked: bool
    confidence_tier: str
    confidence_icon: str
    confidence_message: str
    confidence_source: str

# Index of the first data entry step ("Unternehmen" / "Company")
COMPANY_STEP_INDEX = 1

REQUIRED_SUFFIX = " :red[*]"
REQUIRED_PREFIX = ":red[*] "


CONFIDENCE_TIER_DISPLAY: dict[str, dict[str, object]] = {
    ConfidenceTier.RULE_STRONG.value: {
        "icon": "🔎",
        "color": "blue",
        "label": (
            "Im Originaltext erkannt (regelbasierte Extraktion)",
            "Pattern match in source text",
        ),
        "source": "rule",
    },
    ConfidenceTier.AI_ASSISTED.value: {
        "icon": "🤖",
        "color": "violet",
        "label": (
            "Von der KI ergänzt (bitte prüfen)",
            "Inferred by AI",
        ),
        "source": "llm",
    },
}


SKILL_ALIAS_MAP: dict[str, str] = {
    "requirements hard skills required": "requirements.hard_skills_required",
    "required hard skills": "requirements.hard_skills_required",
    "pflicht hard skills": "requirements.hard_skills_required",
    "hard skill must have": "requirements.hard_skills_required",
    "hard skills must have": "requirements.hard_skills_required",
    "hard skills muss": "requirements.hard_skills_required",
    "hard skill muss": "requirements.hard_skills_required",
    "requirements hard skills optional": "requirements.hard_skills_optional",
    "optional hard skills": "requirements.hard_skills_optional",
    "hard skill nice to have": "requirements.hard_skills_optional",
    "nice to have hard skills": "requirements.hard_skills_optional",
    "hard skills nice to have": "requirements.hard_skills_optional",
    "requirements soft skills required": "requirements.soft_skills_required",
    "required soft skills": "requirements.soft_skills_required",
    "pflicht soft skills": "requirements.soft_skills_required",
    "soft skill must have": "requirements.soft_skills_required",
    "soft skills must have": "requirements.soft_skills_required",
    "soft skills muss": "requirements.soft_skills_required",
    "soft skill muss": "requirements.soft_skills_required",
    "requirements soft skills optional": "requirements.soft_skills_optional",
    "optional soft skills": "requirements.soft_skills_optional",
    "soft skill nice to have": "requirements.soft_skills_optional",
    "nice to have soft skills": "requirements.soft_skills_optional",
    "soft skills nice to have": "requirements.soft_skills_optional",
    "requirements tools and technologies": "requirements.tools_and_technologies",
    "tools tech": "requirements.tools_and_technologies",
    "tools und tech": "requirements.tools_and_technologies",
    "tools & tech": "requirements.tools_and_technologies",
    "tools and tech": "requirements.tools_and_technologies",
    "requirements certifications": "requirements.certificates",
    "requirements certificates": "requirements.certificates",
    "certificates": "requirements.certificates",
    "zertifikate": "requirements.certificates",
    "zertifizierungen": "requirements.certificates",
    "requirements languages required": "requirements.languages_required",
    "languages required": "requirements.languages_required",
    "pflicht sprachen": "requirements.languages_required",
    "languages must have": "requirements.languages_required",
    "sprachen": "requirements.languages_required",
    "requirements languages optional": "requirements.languages_optional",
    "languages optional": "requirements.languages_optional",
    "optionale sprachen": "requirements.languages_optional",
    "languages nice to have": "requirements.languages_optional",
}

REQUIREMENT_OVERVIEW_ROWS: list[tuple[str | None, str | None]] = [
    ("requirements.hard_skills_required", "hard"),
    ("requirements.hard_skills_optional", "hard"),
    (None, None),
    ("requirements.soft_skills_required", "soft"),
    ("requirements.soft_skills_optional", "soft"),
    (None, None),
    ("requirements.tools_and_technologies", "tool"),
    ("requirements.certificates", "certificate"),
    ("requirements.languages_required", "language"),
    ("requirements.languages_optional", "language"),
]

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
.summary-field-title {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.summary-source-icon {
    font-size: 0.9em;
    cursor: help;
}
</style>
"""

FONT_CHOICES = ["Helvetica", "Arial", "Times New Roman", "Georgia", "Calibri"]

CEFR_LANGUAGE_LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2", "Native"]


class _SafeFormatDict(dict[str, str]):
    """Mapping that never raises ``KeyError`` during ``str.format_map`` calls."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - defensive fallback
        return ""


LangPair = tuple[str, str]
LangSuggestionPair = tuple[Sequence[str], Sequence[str]]


class TargetedPromptConfig(TypedDict, total=False):
    """Configuration for inline critical field prompts."""

    prompt: LangPair
    description: LangPair
    suggestions: LangSuggestionPair
    style: Literal["info", "warning"]
    priority: Literal["critical", "normal"]


CRITICAL_FIELD_PROMPTS: dict[str, TargetedPromptConfig] = {
    "company.name": {
        "prompt": (
            "Wie lautet der offizielle Firmenname?",
            "What is the official company name?",
        ),
        "description": (
            "Bitte den rechtlichen oder bevorzugten Namen angeben, damit wir korrekt referenzieren können.",
            "Provide the legal or preferred name so we can reference the company correctly.",
        ),
        "suggestions": (
            ["Noch vertraulich", "Name wird nachgereicht"],
            ["Confidential for now", "Name to be confirmed"],
        ),
        "style": "warning",
    },
    "position.job_title": {
        "prompt": (
            "Welcher Jobtitel soll in der Ausschreibung stehen?",
            "What job title should appear in the posting?",
        ),
        "description": (
            "Ein klarer Jobtitel hilft der KI bei allen weiteren Vorschlägen.",
            "A clear job title helps the assistant with every downstream suggestion.",
        ),
        "suggestions": (
            ["Software Engineer", "Sales Manager", "Product Manager"],
            ["Software Engineer", "Sales Manager", "Product Manager"],
        ),
        "style": "info",
    },
    "position.role_summary": {
        "prompt": (
            "Wie würdest du die Rolle in 2-3 Sätzen beschreiben?",
            "How would you summarise the role in 2-3 sentences?",
        ),
        "description": (
            "Diese Kurzbeschreibung landet sowohl in Follow-ups als auch im Job-Ad-Entwurf.",
            "We use this short blurb in follow-ups and the job ad draft.",
        ),
        "suggestions": (
            [
                "Treibt den Aufbau datengetriebener Produkte voran",
                "Koordiniert funktionsübergreifende Projektteams",
            ],
            [
                "Drives the build-out of data-driven products",
                "Coordinates cross-functional project teams",
            ],
        ),
        "style": "info",
    },
    "location.country": {
        "prompt": (
            "In welchem Land ist die Rolle verortet?",
            "Which country is this role based in?",
        ),
        "description": (
            "Das Land steuert Gehaltsbenchmarks, Benefits und Sprachvorschläge.",
            "Country selection powers salary ranges, benefits, and language suggestions.",
        ),
        "suggestions": (
            ["Deutschland", "Österreich", "Schweiz"],
            ["Germany", "Austria", "Switzerland"],
        ),
        "style": "warning",
    },
    "requirements.hard_skills_required": {
        "prompt": (
            "Welche Hard Skills sind zwingend?",
            "Which hard skills are must-haves?",
        ),
        "description": (
            "Bitte Kerntechnologien oder Tools nennen – das fokussiert unsere Vorschläge.",
            "List the core technologies or tools so our suggestions stay focused.",
        ),
        "suggestions": (
            ["Python, SQL, ETL", "AWS, Terraform, CI/CD"],
            ["Python, SQL, ETL", "AWS, Terraform, CI/CD"],
        ),
        "style": "warning",
    },
    "requirements.soft_skills_required": {
        "prompt": (
            "Welche Soft Skills sind unverzichtbar?",
            "Which soft skills are non-negotiable?",
        ),
        "description": (
            "Stichworte reichen – wir übernehmen die Formulierung im Jobprofil.",
            "Short bullet points are enough – we will phrase them for the profile.",
        ),
        "suggestions": (
            [
                "Kommunikationsstark, teamorientiert, lösungsorientiert",
                "Selbstständig, proaktiv, kundenorientiert",
            ],
            [
                "Strong communicator, collaborative, solution-oriented",
                "Self-driven, proactive, customer-focused",
            ],
        ),
        "style": "info",
    },
}


def _sanitize_template_value(value: Any) -> str:
    """Return a safe string representation for template rendering."""

    if value is None:
        return ""
    if isinstance(value, str):
        sanitized = value.strip()
    else:
        sanitized = str(value)
    return sanitized.replace("{", "").replace("}", "")


def _build_profile_context(profile: Mapping[str, Any]) -> dict[str, str]:
    """Collect frequently reused profile fields for dynamic UI messaging."""

    def _get(path: str) -> str:
        value: Any = profile
        for part in path.split("."):
            if isinstance(value, Mapping):
                value = value.get(part)
            else:
                return ""
        if isinstance(value, str):
            return _sanitize_template_value(value)
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return _sanitize_template_value(value)
        return ""

    job_title = _get("position.job_title")
    company_name = _get("company.name")
    primary_city = _get("location.primary_city")
    country = _get("location.country")

    location_combined = ", ".join(
        part for part in (primary_city, country) if part
    )

    context: dict[str, str] = {
        "job_title": job_title,
        "company_name": company_name,
        "primary_city": primary_city,
        "country": country,
        "location_combined": location_combined,
    }

    return context


def _format_dynamic_message(
    *,
    default: tuple[str, str],
    context: Mapping[str, str],
    variants: Sequence[tuple[tuple[str, str], Sequence[str]]],
) -> str:
    """Return a localized message, injecting context when available."""

    lang = st.session_state.get("lang", "de")
    lang_index = 0 if lang == "de" else 1
    default_text = default[lang_index]
    safe_context = _SafeFormatDict({k: v for k, v in context.items() if v})

    for (de_template, en_template), required_keys in variants:
        if all(safe_context.get(key) for key in required_keys):
            template = de_template if lang_index == 0 else en_template
            try:
                return template.format_map(safe_context)
            except Exception:  # pragma: no cover - robust fallback
                continue
    return default_text


def _get_profile_state() -> dict[str, Any]:
    """Return the mutable profile dict from session state, ensuring it exists."""

    profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, dict):
        return profile
    ensure_state()
    profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, dict):
        return profile
    if isinstance(profile, Mapping):
        coerced = dict(profile)
        st.session_state[StateKeys.PROFILE] = coerced
        return coerced
    fallback = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.PROFILE] = fallback
    return fallback

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


_SIZE_REGEX = re.compile(
    r"((?:über|mehr als|rund|circa|ca\.?|etwa|ungefähr|around|approx(?:\.?|imately)?|knapp|more than)\s+)?"
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?)"
    r"(?:\s*(?:[-–]\s*)\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?)?"
    r"\s*(Mitarbeiter(?:innen)?|Mitarbeitende|Beschäftigte[n]?|Angestellte|Menschen|people|employees|staff)",
    re.IGNORECASE,
)


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


def _normalise_company_page_url(url: str) -> str:
    """Return a normalised URL for caching company sub-pages."""

    candidate = (url or "").strip()
    if not candidate:
        return ""
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return candidate
    path = parsed.path or "/"
    normalised_path = re.sub(r"/{2,}", "/", path)
    if normalised_path != "/" and normalised_path.endswith("/"):
        normalised_path = normalised_path.rstrip("/")
    rebuilt = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=normalised_path or "/",
        fragment="",
    ).geturl()
    return rebuilt


def _hash_text(value: str) -> str:
    """Return a short, deterministic hash for ``value``."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _get_company_page_text_cache() -> dict[str, str]:
    """Return the mutable cache storing raw company page text samples."""

    cache = st.session_state.get(StateKeys.COMPANY_PAGE_TEXT_CACHE)
    if isinstance(cache, dict):
        return cache
    cache = {}
    st.session_state[StateKeys.COMPANY_PAGE_TEXT_CACHE] = cache
    return cache


def _remember_company_page_text(cache_key: str, text: str) -> None:
    """Persist ``text`` for ``cache_key`` in the in-memory session cache."""

    _get_company_page_text_cache()[cache_key] = text


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_fetch_company_page_text(url: str) -> str:
    """Return page text for ``url`` with shared caching."""

    document = extract_text_from_url(url)
    return document.text or ""


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_summarize_company_page(url: str, text_hash: str, label: str, lang: str) -> str:
    """Summarise a company page using cached fetch & deterministic keys."""

    text = _cached_fetch_company_page_text(url)
    return summarize_company_page(text, label, lang=lang)


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_extract_company_info(sample_hash: str) -> Mapping[str, Any]:
    """Return structured company info for the stored sample hash."""

    cache = _get_company_page_text_cache()
    text = cache.get(sample_hash)
    if not isinstance(text, str) or not text.strip():
        return {}
    return extract_company_info(text)


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
        cache_url = _normalise_company_page_url(candidate)
        if not cache_url:
            continue
        try:
            content = _cached_fetch_company_page_text(cache_url)
        except ValueError:
            continue
        content = content.strip()
        if content:
            return cache_url, content
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
        text_cache = st.session_state.get(StateKeys.COMPANY_PAGE_TEXT_CACHE)
        if isinstance(text_cache, dict):
            text_cache.clear()
        _cached_fetch_company_page_text.clear()
        _cached_summarize_company_page.clear()
        _cached_extract_company_info.clear()


def _extract_company_size(text: str) -> str | None:
    """Return a human-readable size snippet from ``text`` if present."""

    if not text:
        return None
    cleaned = text.replace("\xa0", " ")
    normalised = re.sub(r"\s+", " ", cleaned)
    match = _SIZE_REGEX.search(normalised)
    if not match:
        return None
    value = match.group(0)
    return re.sub(r"\s+", " ", value).strip(" .,;") or None


def _record_company_page_source(
    field: str,
    value: str,
    *,
    source_url: str | None,
    section_key: str,
    section_label: str | None,
) -> None:
    """Store metadata describing a company page derived value."""

    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
    rules = metadata.get("rules")
    if isinstance(rules, Mapping):
        updated_rules = dict(rules)
    else:
        updated_rules = {}
    entry = dict(updated_rules.get(field) or {})
    entry.update(
        {
            "rule": f"company_page.{section_key}",
            "value": value,
            "source_text": _truncate_snippet(value),
            "source_kind": "company_page",
            "source_section": section_key,
            "source_section_label": section_label,
            "source_url": source_url,
            "inferred": True,
        }
    )
    updated_rules[field] = entry
    metadata["rules"] = updated_rules
    llm_fields = metadata.get("llm_fields")
    current = {field}
    if isinstance(llm_fields, list):
        current.update({item for item in llm_fields if isinstance(item, str)})
    metadata["llm_fields"] = sorted(current)
    st.session_state[StateKeys.PROFILE_METADATA] = metadata


def _enrich_company_profile_from_about(
    text: str,
    *,
    source_url: str | None = None,
    section_label: str | None = None,
) -> None:
    """Populate missing company fields from an about-page text."""

    if not text.strip():
        return
    profile = st.session_state.get(StateKeys.PROFILE)
    if not isinstance(profile, dict):
        return
    company = profile.get("company")
    if not isinstance(company, dict):
        return

    sample = text.strip()
    if len(sample) > 12000:
        sample = sample[:12000]

    try:
        sample_hash = _hash_text(sample)
        _remember_company_page_text(sample_hash, sample)
        extracted = _cached_extract_company_info(sample_hash)
    except Exception:
        extracted = {}

    if isinstance(extracted, dict):
        mapping = {
            "name": "name",
            "location": "hq_location",
            "mission": "mission",
        }
        for source, target in mapping.items():
            if target not in company or not str(company.get(target, "")).strip():
                value = extracted.get(source)
                if isinstance(value, str) and value.strip():
                    normalized = value.strip()
                    company[target] = normalized
                    _record_company_page_source(
                        f"company.{target}",
                        normalized,
                        source_url=source_url,
                        section_key="about",
                        section_label=section_label,
                    )

    if "size" not in company or not str(company.get("size", "")).strip():
        size_value = _extract_company_size(text)
        if size_value:
            company["size"] = size_value
            _record_company_page_source(
                "company.size",
                size_value,
                source_url=source_url,
                section_key="about",
                section_label=section_label,
            )


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
        text_hash = _hash_text(text)
        summary = _cached_summarize_company_page(url, text_hash, label, lang)
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
    summaries[section_key] = {"url": url, "summary": summary, "label": label}
    if section_key == "about":
        _enrich_company_profile_from_about(
            text, source_url=url, section_label=label
        )
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


def _request_scroll_to_top() -> None:
    """Flag that the next render should scroll to the top."""

    st.session_state[StateKeys.SCROLL_TO_TOP] = True


def _apply_pending_scroll_reset() -> None:
    """Inject JavaScript to scroll to the top if requested."""

    if st.session_state.pop(StateKeys.SCROLL_TO_TOP, False):
        st.markdown(
            """
            <script>
                window.scrollTo({top: 0, behavior: 'smooth'});
            </script>
            """,
            unsafe_allow_html=True,
        )


def next_step() -> None:
    """Advance the wizard to the next step."""

    current = st.session_state.get(StateKeys.STEP, 0)
    total_steps = st.session_state.get(StateKeys.WIZARD_STEP_COUNT, current + 2)
    total_steps = max(total_steps, current + 2)
    _request_scroll_to_top()
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
    completed = set(st.session_state.get(StateKeys.COMPLETED_SECTIONS, []))
    candidate = min(current + 1, total_steps - 1)
    while candidate < total_steps - 1 and candidate in completed:
        candidate += 1
    st.session_state[StateKeys.STEP] = min(candidate, total_steps - 1)


def prev_step() -> None:
    """Return to the previous wizard step."""

    _request_scroll_to_top()
    st.session_state[StateKeys.STEP] = max(
        0, st.session_state.get(StateKeys.STEP, 0) - 1
    )


def on_file_uploaded() -> None:
    """Handle file uploads and populate job posting text."""

    f = st.session_state.get(UIKeys.PROFILE_FILE_UPLOADER)
    if not f:
        return
    try:
        doc = clean_structured_document(extract_text_from_file(f))
        txt = doc.text
    except ValueError as e:
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
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
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
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
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
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
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        return
    st.session_state["__prefill_profile_text__"] = txt
    st.session_state["__prefill_profile_doc__"] = doc
    st.session_state[StateKeys.RAW_BLOCKS] = doc.blocks
    st.session_state["__run_extraction__"] = True


def on_url_changed() -> None:
    """Fetch text from URL and populate job posting text."""

    url = st.session_state.get(UIKeys.PROFILE_URL_INPUT, "").strip()
    if not url:
        return
    if not is_supported_url(url):
        display_error(
            tr(
                "Ungültige URL – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Invalid URL – you can also enter the information manually in the following steps.",
            )
        )
        st.session_state["source_error"] = True
        return
    try:
        doc = clean_structured_document(extract_text_from_url(url))
        txt = doc.text
    except Exception as e:  # pragma: no cover - defensive
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
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
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        return
    st.session_state["__prefill_profile_text__"] = txt
    st.session_state["__prefill_profile_doc__"] = doc
    st.session_state[StateKeys.RAW_BLOCKS] = doc.blocks
    st.session_state["__run_extraction__"] = True


def _autodetect_lang(text: str) -> None:
    """Detect language from ``text`` and update session language."""

    if not text:
        return
    try:
        from langdetect import detect

        detected = detect(text)
        if detected.startswith("en"):
            st.session_state["lang"] = "en"
        metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
        if not isinstance(metadata, dict):  # pragma: no cover - defensive guard
            metadata = {}
        metadata = dict(metadata)
        metadata["autodetect_language"] = detected
        st.session_state[StateKeys.PROFILE_METADATA] = metadata
    except Exception:  # pragma: no cover - best effort
        pass
def _annotate_rule_metadata(
    rule_meta: Mapping[str, Mapping[str, Any]] | None,
    blocks: Sequence[ContentBlock],
    doc: StructuredDocument | None,
) -> dict[str, dict[str, Any]]:
    """Augment rule metadata with document context."""

    annotated: dict[str, dict[str, Any]] = {}
    source = getattr(doc, "source", None)
    for field, payload in (rule_meta or {}).items():
        if not isinstance(payload, Mapping):
            continue
        entry = dict(payload)
        if source:
            entry.setdefault("document_source", source)
        block_index = entry.get("block_index")
        if isinstance(block_index, int) and 0 <= block_index < len(blocks):
            block = blocks[block_index]
            entry.setdefault("block_type", block.type)
            metadata = block.metadata or {}
            page = metadata.get("page")
            if isinstance(page, int):
                entry.setdefault("page", page)
        entry.setdefault("source_kind", "job_posting")
        annotated[field] = entry
    return annotated


def _build_llm_metadata(
    extracted: Mapping[str, Any],
    rule_matches: Mapping[str, Any],
    doc: StructuredDocument | None,
) -> dict[str, dict[str, Any]]:
    """Create metadata entries for values inferred by the LLM fallback."""

    llm_entries: dict[str, dict[str, Any]] = {}
    source = getattr(doc, "source", None)
    for field, value in flatten(dict(extracted)).items():
        if field in rule_matches:
            continue
        normalized = _normalize_semantic_empty(value)
        if normalized is None:
            continue
        entry: dict[str, Any] = {
            "rule": "llm.extract_json",
            "value": normalized,
            "inferred": True,
            "source_kind": "job_posting",
        }
        snippet = _truncate_snippet(normalized)
        if snippet:
            entry["source_text"] = snippet
        if source:
            entry["document_source"] = source
        llm_entries[field] = entry
    return llm_entries


def _extract_and_summarize(text: str, schema: dict) -> None:
    """Run extraction on ``text`` and store profile, summary, and missing fields."""

    raw_blocks = st.session_state.get(StateKeys.RAW_BLOCKS, []) or []
    doc: StructuredDocument | None = st.session_state.get("__prefill_profile_doc__")
    rule_matches = apply_rules(raw_blocks)
    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
    confidence_map = _ensure_mapping(metadata.get("field_confidence"))
    if rule_matches:
        rule_patch = matches_to_patch(rule_matches)
        st.session_state[StateKeys.PROFILE] = rule_patch
        st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = rule_patch
        new_meta = build_rule_metadata(rule_matches)
        annotated_rules = _annotate_rule_metadata(
            new_meta.get("rules"), raw_blocks, doc
        )
        existing_rules = metadata.get("rules") or {}
        if not isinstance(existing_rules, Mapping):
            existing_rules = {}
        combined_rules = {**dict(existing_rules), **annotated_rules}
        locked = set(metadata.get("locked_fields", [])) | set(
            new_meta.get("locked_fields", [])
        )
        high_conf = set(metadata.get("high_confidence_fields", [])) | set(
            new_meta.get("high_confidence_fields", [])
        )
        confidence_map.update(_ensure_mapping(new_meta.get("field_confidence")))
        metadata["rules"] = combined_rules
        metadata["locked_fields"] = sorted(locked)
        metadata["high_confidence_fields"] = sorted(high_conf)
    else:
        metadata.setdefault("rules", {})
        metadata.setdefault("locked_fields", [])
        metadata.setdefault("high_confidence_fields", [])
    metadata["field_confidence"] = confidence_map

    vector_store_id = st.session_state.get("vector_store_id") or None

    url_hint: str | None = None
    if doc and doc.source:
        parsed = urlparse(doc.source)
        if parsed.scheme in {"http", "https"}:
            url_hint = doc.source

    def _normalize_hint(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
        else:
            normalized = str(value).strip()
        return normalized or None

    existing_profile = st.session_state.get(StateKeys.PROFILE, {})

    def _locked_hint(field: str) -> str | None:
        locked_fields = set(metadata.get("locked_fields") or [])
        if field not in locked_fields:
            return None
        rules_meta: Mapping[str, Mapping[str, Any]] = metadata.get("rules") or {}
        meta_value = rules_meta.get(field, {}).get("value")
        if meta_value is not None:
            return _normalize_hint(meta_value)
        match = rule_matches.get(field)
        if match and match.value is not None:
            return _normalize_hint(match.value)
        return _normalize_hint(get_in(existing_profile, field, None))

    locked_hints: dict[str, str] = {}
    for field in metadata.get("locked_fields", []) or []:
        hint_value = _locked_hint(field)
        if hint_value is not None:
            locked_hints[field] = hint_value

    title_hint = locked_hints.get("position.job_title")
    company_hint = locked_hints.get("company.name")

    raw_json = extract_json(
        text,
        title=title_hint,
        company=company_hint,
        url=url_hint,
        locked_fields=locked_hints or None,
    )
    try:
        extracted_data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        start = raw_json.find("{")
        end = raw_json.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model returned invalid JSON") from exc
        fragment = raw_json[start : end + 1]
        extracted_data = json.loads(fragment)
    if not isinstance(extracted_data, dict):
        raise ValueError("Model returned JSON that is not an object.")

    llm_meta = _build_llm_metadata(extracted_data, rule_matches, doc)
    if llm_meta:
        existing_rules = metadata.get("rules")
        if not isinstance(existing_rules, Mapping):
            existing_rules = {}
        merged_rules = dict(existing_rules)
        for field, entry in llm_meta.items():
            merged_rules.setdefault(field, entry)
        metadata["rules"] = merged_rules
        current_llm = metadata.get("llm_fields")
        llm_fields = {field for field in llm_meta}
        if isinstance(current_llm, list):
            llm_fields.update({field for field in current_llm if isinstance(field, str)})
        metadata["llm_fields"] = sorted(llm_fields)

    for field, match in rule_matches.items():
        set_in(extracted_data, field, match.value)

    profile = coerce_and_fill(extracted_data)
    profile = apply_basic_fallbacks(profile, text, metadata=metadata)
    lang = getattr(st.session_state, "lang", "en") or "en"
    occupation_meta: dict[str, str] | None = None
    essential_skills: list[str] = []
    job_title_value = (profile.position.job_title or "").strip()
    if job_title_value:
        occupation_meta = classify_occupation(job_title_value, lang=lang)
        if occupation_meta:
            label = str(occupation_meta.get("preferredLabel") or "").strip()
            uri = str(occupation_meta.get("uri") or "").strip()
            group = str(occupation_meta.get("group") or "").strip()

            normalized_meta = dict(occupation_meta)
            if label:
                normalized_meta["preferredLabel"] = label
            if uri:
                normalized_meta["uri"] = uri
            if group:
                normalized_meta["group"] = group
            occupation_meta = normalized_meta

            if label:
                profile.position.occupation_label = label
            profile.position.occupation_uri = uri or None
            profile.position.occupation_group = group or None

            essential_skills = (
                get_essential_skills(uri, lang=lang) if uri else []
            )

    if occupation_meta:
        st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] = [occupation_meta]
    else:
        st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] = []

    data = profile.model_dump()
    for path, value in flatten(data).items():
        if not _is_meaningful_value(value):
            continue
        confidence_map.setdefault(
            path,
            {
                "tier": DEFAULT_AI_TIER.value,
                "source": "llm",
                "score": None,
            },
        )
    metadata["field_confidence"] = confidence_map
    st.session_state[StateKeys.PROFILE] = data
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = data
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
            data.get("requirements", {}).get("hard_skills_required", [])
        ),
        "nice": _unique_normalized(
            data.get("requirements", {}).get("hard_skills_optional", [])
        ),
    }
    st.session_state[StateKeys.ESCO_SKILLS] = essential_skills
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = summary
    missing: list[str] = []
    for field in CRITICAL_FIELDS:
        if not get_in(data, field, None):
            missing.append(field)
    metadata["rag"] = {
        "vector_store_id": vector_store_id or "",
        "fields": {},
        "global_context": [],
        "answers": {},
    }
    st.session_state[StateKeys.PROFILE_METADATA] = metadata
    if st.session_state.get("auto_reask"):
        if not missing:
            st.session_state["auto_reask_round"] = 0
            st.session_state["auto_reask_total"] = 0
            st.session_state.pop(StateKeys.FOLLOWUPS, None)
        else:
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

    first_incomplete, _completed = _update_section_progress()
    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = bool(first_incomplete)


def _maybe_run_extraction(schema: dict) -> None:
    """Trigger extraction when the corresponding flag is set in session state."""

    should_run = st.session_state.pop("__run_extraction__", False)
    if not should_run:
        return

    doc: StructuredDocument | None = st.session_state.get("__prefill_profile_doc__")
    raw_input = st.session_state.get(StateKeys.RAW_TEXT, "")
    if not raw_input:
        raw_input = st.session_state.get("__prefill_profile_text__", "")
    raw_input = raw_input or ""
    if (
        doc
        and raw_input
        and raw_input.strip()
        and raw_input.strip() != doc.text.strip()
    ):
        doc = None
    if not raw_input and doc:
        raw_input = doc.text
    if doc is None:
        doc = build_plain_text_document(raw_input, source="manual")
    cleaned_doc = clean_structured_document(doc)
    raw_clean = cleaned_doc.text
    if not raw_clean.strip():
        st.session_state["_analyze_attempted"] = True
        st.session_state.pop("__last_extracted_hash__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
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
    st.session_state[StateKeys.RAW_BLOCKS] = cleaned_doc.blocks
    st.session_state["__prefill_profile_doc__"] = cleaned_doc
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
    st.session_state[StateKeys.RAW_BLOCKS] = []
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
    st.session_state[StateKeys.EXTRACTION_MISSING] = []
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {}
    st.session_state[StateKeys.ESCO_SKILLS] = []
    st.session_state[StateKeys.SKILL_BUCKETS] = {"must": [], "nice": []}
    st.session_state[StateKeys.COMPLETED_SECTIONS] = []
    st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] = None
    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = False
    st.session_state.pop("_analyze_attempted", None)
    st.session_state.pop("__last_extracted_hash__", None)
    st.session_state.pop("__prefill_profile_doc__", None)
    _request_scroll_to_top()
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

    _merge_requirement_aliases()
    section_entries = build_prefilled_sections(
        include_prefixes=include_prefixes,
        exclude_prefixes=exclude_prefixes,
    )
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


def _normalize_alias_key(name: str) -> str:
    """Return a normalized identifier for alias lookups."""

    return re.sub(r"[^0-9a-z]+", " ", name.casefold()).strip()


def _merge_requirement_aliases() -> None:
    """Merge legacy or localized requirement keys into canonical schema fields."""

    profile = st.session_state.get(StateKeys.PROFILE)
    raw_profile = st.session_state.get(StateKeys.EXTRACTION_RAW_PROFILE)
    if not isinstance(profile, dict):
        return

    aggregated: dict[str, list[str]] = defaultdict(list)
    alias_hits: dict[str, set[str]] = defaultdict(set)

    for source in (raw_profile, profile):
        if not isinstance(source, dict):
            continue
        for path, value in flatten(source).items():
            normalized = _normalize_alias_key(path)
            target = SKILL_ALIAS_MAP.get(normalized)
            if not target:
                continue
            aggregated[target].extend(_normalize_list(value))
            alias_hits[target].add(path)

    if not aggregated:
        return

    for target, values in aggregated.items():
        cleaned = _unique_normalized(values)
        if not cleaned:
            continue
        _update_profile(target, cleaned)
        if isinstance(raw_profile, dict):
            set_in(raw_profile, target, cleaned)
        for alias in alias_hits.get(target, set()):
            if alias == target:
                continue
            if isinstance(raw_profile, dict):
                _delete_path(raw_profile, alias)
            _delete_path(profile, alias)

    if isinstance(raw_profile, dict):
        st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = raw_profile
    st.session_state[StateKeys.PROFILE] = profile


# --- Hilfsfunktionen: Dot-Notation lesen/schreiben ---
def _delete_path(d: dict | None, path: str) -> None:
    """Remove the value at ``path`` from ``d`` if it exists."""

    if not isinstance(d, dict) or not path:
        return
    if "." not in path:
        d.pop(path, None)
        return
    parts = path.split(".")
    cursor = d
    for part in parts[:-1]:
        next_cursor = cursor.get(part)
        if not isinstance(next_cursor, dict):
            return
        cursor = next_cursor
    if isinstance(cursor, dict):
        cursor.pop(parts[-1], None)


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


def _job_ad_field_entries(
    data: Mapping[str, Any],
    field: JobAdFieldDefinition,
    lang: str,
) -> list[tuple[str, str]]:
    """Return selectable entry tuples for a job-ad field."""

    is_de = lang.lower().startswith("de")
    yes_no = ("Ja", "Nein") if is_de else ("Yes", "No")

    if field.key == "compensation.salary":
        salary_text = _job_ad_field_value(data, field.key, lang)
        return [(f"{field.key}::0", salary_text)] if salary_text else []

    value = _job_ad_get_value(data, field.key)
    if value in (None, "", []):
        return []

    if field.key == "employment.travel_required":
        detail = _job_ad_get_value(data, "employment.travel_details")
        value = detail if detail else bool(value)
    elif field.key == "employment.relocation_support":
        detail = _job_ad_get_value(data, "employment.relocation_details")
        value = detail if detail else bool(value)
    elif field.key == "employment.work_policy":
        details_text = _job_ad_get_value(data, "employment.work_policy_details")
        if not details_text:
            percentage = _job_ad_get_value(data, "employment.remote_percentage")
            if percentage:
                details_text = (
                    f"{percentage}% Home-Office" if is_de else f"{percentage}% remote"
                )
        if details_text and isinstance(value, str):
            value = f"{value.strip()} ({details_text})"
    elif field.key == "employment.remote_percentage" and value:
        value = f"{value}% Home-Office" if is_de else f"{value}% remote"

    if isinstance(value, list):
        items = _normalize_list(value)
        if field.key == "compensation.benefits":
            deduped: list[str] = []
            seen: set[str] = set()
            for entry in items:
                lowered = entry.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    deduped.append(entry)
            items = deduped
        return [(f"{field.key}::{idx}", item) for idx, item in enumerate(items) if item]

    if isinstance(value, bool):
        label = yes_no[0] if value else yes_no[1]
        return [(f"{field.key}::0", label)]

    if isinstance(value, (int, float)):
        return [(f"{field.key}::0", str(value))]

    if isinstance(value, str):
        text = value.strip()
        return [(f"{field.key}::0", text)] if text else []

    return [(f"{field.key}::0", str(value))]


def _job_ad_available_field_keys(
    data: Mapping[str, Any],
    lang: str,
) -> set[str]:
    """Return all job-ad field keys that currently have captured values."""

    available: set[str] = set()
    for field in JOB_AD_FIELDS:
        if _job_ad_field_entries(data, field, lang):
            available.add(field.key)
    return available


def _update_job_ad_font() -> None:
    """Persist the selected export font in session state."""

    selected = st.session_state.get(UIKeys.JOB_AD_FONT)
    if selected:
        st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = selected


def _prepare_job_ad_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied profile for job-ad generation."""

    base = dict(data) if not isinstance(data, dict) else data
    return deepcopy(base)


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
    container = st.container()
    with container:
        st.markdown(f"<div id='{anchor}'></div>", unsafe_allow_html=True)
    if key not in st.session_state:
        st.session_state[key] = ""
    ui_variant = q.get("ui_variant")
    description = q.get("description")
    if ui_variant in ("info", "warning") and description:
        getattr(container, ui_variant)(description)
    elif description:
        container.caption(description)
    if q.get("priority") == "critical":
        with container:
            st.markdown(f"{REQUIRED_PREFIX}**{prompt}**")
    else:
        with container:
            st.markdown(f"**{prompt}**")
    if suggestions:
        cols = container.columns(len(suggestions))
        for i, (col, sug) in enumerate(zip(cols, suggestions)):
            if col.button(sug, key=f"{key}_opt_{i}"):
                st.session_state[key] = sug
    with container:
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


def _lang_index(lang: str | None) -> int:
    """Return index for language-dependent tuples (0=de, 1=en)."""

    if not lang:
        return 0
    return 0 if lang.lower().startswith("de") else 1


def _select_lang_text(pair: LangPair | None, lang: str | None) -> str:
    """Return the language-specific string from ``pair``."""

    if not pair:
        return ""
    idx = _lang_index(lang)
    return pair[idx] if idx < len(pair) else pair[0]


def _select_lang_suggestions(
    pair: LangSuggestionPair | None, lang: str | None
) -> list[str]:
    """Return language-specific suggestion list from ``pair``."""

    if not pair:
        return []
    idx = _lang_index(lang)
    if idx >= len(pair):
        idx = 0
    return list(pair[idx])


def _ensure_targeted_followup(field: str) -> None:
    """Ensure a targeted follow-up question exists for ``field`` if configured."""

    config = CRITICAL_FIELD_PROMPTS.get(field)
    if not config:
        return
    existing = list(st.session_state.get(StateKeys.FOLLOWUPS) or [])
    if any(q.get("field") == field for q in existing):
        return
    lang = getattr(st.session_state, "lang", None) or st.session_state.get(
        UIKeys.LANG_SELECT,
        "de",
    )
    followup = {
        "field": field,
        "question": _select_lang_text(config.get("prompt"), lang),
        "priority": config.get("priority", "critical"),
        "suggestions": _select_lang_suggestions(config.get("suggestions"), lang),
    }
    description = _select_lang_text(config.get("description"), lang)
    if description:
        followup["description"] = description
    style = config.get("style")
    if style:
        followup["ui_variant"] = style
    existing.insert(0, followup)
    st.session_state[StateKeys.FOLLOWUPS] = existing


def _missing_fields_for_section(section_index: int) -> list[str]:
    """Return missing critical fields for a given section and enqueue prompts."""

    missing = st.session_state.get(StateKeys.EXTRACTION_MISSING)
    if missing is None:
        missing = get_missing_critical_fields()
    section_missing = [
        field
        for field in missing
        if FIELD_SECTION_MAP.get(field) == section_index
    ]
    for field in section_missing:
        _ensure_targeted_followup(field)
    return section_missing


def _generate_job_ad_content(
    filtered_profile: Mapping[str, Any],
    selected_fields: Collection[str],
    target_value: str | None,
    manual_entries: Sequence[dict[str, str]],
    style_reference: str | None,
    lang: str,
    *,
    show_error: bool = True,
) -> bool:
    """Generate the job ad and update session state."""

    if not selected_fields or not target_value:
        return False

    def _generate_sync() -> str:
        return generate_job_ad(
            filtered_profile,
            list(selected_fields),
            target_audience=target_value,
            manual_sections=list(manual_entries),
            style_reference=style_reference,
            tone=st.session_state.get(UIKeys.TONE_SELECT),
            lang=lang,
            selected_values=st.session_state.get(
                StateKeys.JOB_AD_SELECTED_VALUES, {}
            ),
        )

    job_ad_md = ""
    placeholder = st.empty()
    spinner_label = tr("Anzeige wird generiert…", "Generating job ad…")

    try:
        stream, fallback_doc = stream_job_ad(
            filtered_profile,
            list(selected_fields),
            target_audience=target_value,
            manual_sections=list(manual_entries),
            style_reference=style_reference,
            tone=st.session_state.get(UIKeys.TONE_SELECT),
            lang=lang,
            selected_values=st.session_state.get(
                StateKeys.JOB_AD_SELECTED_VALUES, {}
            ),
        )
    except Exception:
        try:
            job_ad_md = _generate_sync()
            placeholder.markdown(job_ad_md)
        except Exception as exc:  # pragma: no cover - error path
            if show_error:
                st.error(
                    tr(
                        "Job Ad Generierung fehlgeschlagen",
                        "Job ad generation failed",
                    )
                    + f": {exc}"
                )
            return False
    else:
        chunks: list[str] = []
        try:
            with st.spinner(spinner_label):
                for chunk in stream:
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    placeholder.markdown("".join(chunks))
        except Exception as exc:  # pragma: no cover - network/SDK issues
            if show_error:
                st.error(
                    tr(
                        "Job Ad Streaming fehlgeschlagen",
                        "Job ad streaming failed",
                    )
                    + f": {exc}"
                )
            try:
                job_ad_md = _generate_sync()
                placeholder.markdown(job_ad_md)
            except Exception as sync_exc:  # pragma: no cover - error path
                if show_error:
                    st.error(
                        tr(
                            "Job Ad Generierung fehlgeschlagen",
                            "Job ad generation failed",
                        )
                        + f": {sync_exc}"
                    )
                return False
        else:
            try:
                result = stream.result
                job_ad_md = (result.content or stream.text or "").strip()
            except RuntimeError:
                job_ad_md = (stream.text or "").strip()
            if not job_ad_md:
                job_ad_md = fallback_doc
            placeholder.markdown(job_ad_md)

    st.session_state[StateKeys.JOB_AD_MD] = job_ad_md
    findings = scan_bias_language(job_ad_md, lang)
    st.session_state[StateKeys.BIAS_FINDINGS] = findings
    return True


def _generate_interview_guide_content(
    profile_payload: Mapping[str, Any],
    lang: str,
    selected_num: int,
    *,
    audience: str = "general",
    warn_on_length: bool = True,
    show_error: bool = True,
) -> bool:
    """Generate the interview guide and update session state."""

    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience
    st.session_state.setdefault(UIKeys.AUDIENCE_SELECT, audience)

    requirements_data = dict(profile_payload.get("requirements", {}) or {})
    extras = (
        len(requirements_data.get("hard_skills_required", []))
        + len(requirements_data.get("hard_skills_optional", []))
        + len(requirements_data.get("soft_skills_required", []))
        + len(requirements_data.get("soft_skills_optional", []))
        + (
            1
            if (profile_payload.get("company", {}) or {}).get("culture")
            else 0
        )
    )

    if warn_on_length and selected_num + extras > 15:
        st.warning(
            tr(
                "Viele Fragen erzeugen einen sehr umfangreichen Leitfaden.",
                "A high question count creates a very long guide.",
            )
        )

    responsibilities_text = "\n".join(
        profile_payload.get("responsibilities", {}).get("items", [])
    )

    try:
        guide = generate_interview_guide(
            job_title=profile_payload.get("position", {}).get("job_title", ""),
            responsibilities=responsibilities_text,
            hard_skills=(
                requirements_data.get("hard_skills_required", [])
                + requirements_data.get("hard_skills_optional", [])
            ),
            soft_skills=(
                requirements_data.get("soft_skills_required", [])
                + requirements_data.get("soft_skills_optional", [])
            ),
            company_culture=profile_payload.get("company", {}).get(
                "culture", ""
            ),
            audience=audience,
            lang=lang,
            tone=st.session_state.get("tone"),
            num_questions=selected_num,
        )
        guide_md = guide.final_markdown()
        st.session_state[StateKeys.INTERVIEW_GUIDE_DATA] = guide.model_dump()
    except Exception as exc:  # pragma: no cover - error path
        if show_error:
            st.error(
                tr(
                    "Interviewleitfaden-Generierung fehlgeschlagen: {error}. Bitte erneut versuchen.",
                    "Interview guide generation failed: {error}. Please try again.",
                ).format(error=exc)
            )
        return False

    st.session_state[StateKeys.INTERVIEW_GUIDE_MD] = guide_md
    return True


def _apply_followup_updates(
    answers: Mapping[str, str],
    *,
    data: dict[str, Any],
    filtered_profile: Mapping[str, Any],
    profile_payload: Mapping[str, Any],
    target_value: str | None,
    manual_entries: Sequence[dict[str, str]],
    style_reference: str | None,
    lang: str,
    selected_fields: Collection[str],
    num_questions: int,
    warn_on_length: bool,
    show_feedback: bool,
) -> tuple[bool, bool]:
    """Persist follow-up answers and refresh derived outputs."""

    for field_path, answer in answers.items():
        stripped = answer.strip()
        if stripped:
            set_in(data, field_path, stripped)

    job_generated = _generate_job_ad_content(
        filtered_profile,
        selected_fields,
        target_value,
        manual_entries,
        style_reference,
        lang,
        show_error=show_feedback,
    )
    audience_choice = (
        st.session_state.get(StateKeys.INTERVIEW_AUDIENCE)
        or st.session_state.get(UIKeys.AUDIENCE_SELECT)
        or "general"
    )
    interview_generated = _generate_interview_guide_content(
        profile_payload,
        lang,
        num_questions,
        audience=audience_choice,
        warn_on_length=warn_on_length,
        show_error=show_feedback,
    )
    return job_generated, interview_generated


def _clear_generated() -> None:
    """Remove cached generated outputs from ``st.session_state``."""

    for key in (
        StateKeys.JOB_AD_MD,
        StateKeys.BOOLEAN_STR,
        StateKeys.INTERVIEW_GUIDE_MD,
        StateKeys.INTERVIEW_GUIDE_DATA,
    ):
        st.session_state.pop(key, None)
    for key in (
        UIKeys.JOB_AD_OUTPUT,
        UIKeys.INTERVIEW_OUTPUT,
    ):
        st.session_state.pop(key, None)


def _normalize_semantic_empty(value: Any) -> Any:
    """Return a canonical representation for semantically empty values."""

    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, (list, tuple, set, frozenset)):
        return None if len(value) == 0 else value
    if isinstance(value, dict):
        return None if len(value) == 0 else value
    return value


def _normalize_value_for_path(path: str, value: Any) -> Any:
    """Apply field-specific normalisation before persisting ``value``."""

    if path == "location.country":
        if isinstance(value, str) or value is None:
            return normalize_country(value)
        return normalize_country(str(value))
    if path in {
        "requirements.languages_required",
        "requirements.languages_optional",
    }:
        if isinstance(value, list):
            return normalize_language_list(value)
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return normalize_language_list(parts)
        return normalize_language_list([])
    return value


def _document_origin_label(source: str | None) -> str | None:
    """Return a compact label describing ``source`` for tooltips."""

    if not source:
        return None
    normalized = source.strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    if lowered == "manual":
        return tr("manuelle Eingabe", "manual input")
    if lowered == "pasted":
        return tr("eingefügter Text", "pasted text")
    if lowered == "merged":
        return tr("kombinierte Quellen", "combined sources")
    parsed = urlparse(normalized)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc.lower()
    name = Path(normalized).name
    return name or normalized


def _company_section_label(section_key: str | None) -> str | None:
    """Return a localized label for known company page sections."""

    if not section_key:
        return None
    mapping: dict[str, tuple[str, str]] = {
        "about": ("Über-uns-Seite", "About page"),
        "imprint": ("Impressum", "Imprint"),
        "press": ("Pressebereich", "Press section"),
    }
    localized = mapping.get(section_key.lower())
    if not localized:
        return None
    return localized[0] if st.session_state.get("lang", "de").startswith("de") else localized[1]


def _truncate_snippet(value: Any, *, limit: int = 220) -> str | None:
    """Return a shortened textual representation for tooltips."""

    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    snippet = " ".join(value.strip().split())
    if not snippet:
        return None
    if len(snippet) > limit:
        snippet = snippet[: limit - 1].rstrip() + "…"
    return snippet


def _resolve_field_source_info(path: str) -> FieldSourceInfo | None:
    """Build source information for ``path`` from stored metadata."""

    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    rules_meta = raw_metadata.get("rules") or {}
    entry = rules_meta.get(path)
    if not isinstance(entry, Mapping):
        return None

    source_kind = str(entry.get("source_kind") or "job_posting")
    snippet = _truncate_snippet(entry.get("source_text"))
    confidence = entry.get("confidence")
    is_inferred = bool(entry.get("inferred"))
    context_bits: list[str] = []
    url: str | None = None

    if source_kind == "company_page":
        section_label = entry.get("source_section_label")
        if not isinstance(section_label, str) or not section_label.strip():
            section_label = _company_section_label(entry.get("source_section"))
        descriptor = tr(
            "Unternehmenswebsite – {section}",
            "Company website – {section}",
        ).format(section=section_label or tr("Unterseite", "subpage"))
        url = entry.get("source_url") or None
        if isinstance(url, str) and url.strip():
            parsed = urlparse(url)
            if parsed.netloc:
                context_bits.append(parsed.netloc.lower())
    else:
        descriptor = _block_descriptor(entry.get("block_type"))
        document_label = _document_origin_label(entry.get("document_source"))
        if document_label:
            context_bits.append(document_label)
        page = entry.get("page")
        if isinstance(page, int):
            context_bits.insert(
                0,
                tr("Seite {page}", "Page {page}").format(page=page),
            )

    context = ", ".join(context_bits) if context_bits else None
    return FieldSourceInfo(
        descriptor=descriptor,
        context=context,
        snippet=snippet,
        confidence=confidence if isinstance(confidence, (int, float)) else None,
        is_inferred=is_inferred,
        url=url,
    )


def _summary_source_icon_html(path: str) -> str:
    """Return HTML snippet for the summary info icon."""

    info = _resolve_field_source_info(path)
    if not info:
        return ""
    tooltip = html.escape(info.tooltip(), quote=True)
    return (
        f"<span class='summary-source-icon' role='img' aria-label='{tooltip}' "
        f"title='{tooltip}'>ℹ️</span>"
    )


def _block_descriptor(block_type: str | None) -> str:
    """Return a localized descriptor for a block type."""

    mapping: dict[str | None, tuple[str, str]] = {
        "heading": ("Stellenanzeige – Überschrift", "Job ad heading"),
        "paragraph": ("Stellenanzeige – Absatz", "Job ad paragraph"),
        "list_item": ("Stellenanzeige – Aufzählungspunkt", "Job ad bullet point"),
        "table": ("Stellenanzeige – Tabellenzeile", "Job ad table row"),
        None: ("Stellenanzeige – Abschnitt", "Job ad snippet"),
    }
    key = block_type if block_type in mapping else None
    label_de, label_en = mapping[key]
    return label_de if st.session_state.get("lang", "de").startswith("de") else label_en


_FIELD_LOCK_BASE_KEY = "ui.locked_field_unlock"


def _field_unlock_key(path: str, context: str) -> str:
    """Return the Streamlit state key used to unlock ``path`` for ``context``."""

    normalized = path.replace(".", "_")
    return f"{_FIELD_LOCK_BASE_KEY}.{context}.{normalized}"


def _merge_help_text(original: str | None, extra: str | None) -> str | None:
    """Combine ``original`` help text with ``extra`` notes if both are present."""

    if original and extra:
        return f"{original}\n\n{extra}"
    return original or extra


def _apply_field_lock_kwargs(
    config: FieldLockConfig, base_kwargs: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Merge lock-specific widget kwargs into ``base_kwargs``."""

    kwargs = dict(base_kwargs or {})
    help_text = config.get("help_text")
    if help_text:
        kwargs["help"] = _merge_help_text(kwargs.get("help"), help_text)
    if config.get("disabled"):
        kwargs["disabled"] = True
    return kwargs


def _confidence_indicator(tier: str) -> tuple[str, str, str]:
    """Return the icon, tooltip, and source for a given confidence ``tier``."""

    info = CONFIDENCE_TIER_DISPLAY.get(tier)
    if not info:
        return "", "", ""

    icon = str(info.get("icon") or "")
    color = str(info.get("color") or "")
    icon_text = f":{color}[{icon}]" if icon and color else icon

    label_data = info.get("label")
    if isinstance(label_data, tuple) and len(label_data) == 2:
        message = tr(label_data[0], label_data[1])
    else:  # pragma: no cover - defensive
        message = ""

    source = str(info.get("source") or "")
    return icon_text, message, source


def _confidence_legend_entries() -> list[tuple[str, str]]:
    """Return localized legend entries for all configured tiers."""

    entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tier in CONFIDENCE_TIER_DISPLAY:
        icon, message, _source = _confidence_indicator(tier)
        key = (icon, message)
        if icon and message and key not in seen:
            entries.append(key)
            seen.add(key)
    return entries


def _render_confidence_legend(
    container: DeltaGenerator | None = None,
) -> None:
    """Render a compact legend that explains confidence indicators."""

    entries = _confidence_legend_entries()
    if not entries:
        return

    container = container or st
    intro = tr("Legende:", "Legend:")
    legend_body = " • ".join(f"{icon} {message}" for icon, message in entries)
    container.caption(f"{intro} {legend_body}")


def _ensure_mapping(value: Any) -> dict[str, Any]:
    """Return ``value`` as a shallow ``dict`` when it is mapping-like."""

    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _is_meaningful_value(value: Any) -> bool:
    """Return ``True`` when ``value`` represents a filled field."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _field_lock_config(
    path: str,
    label: str,
    *,
    container: DeltaGenerator | None = None,
    context: str = "main",
) -> FieldLockConfig:
    """Return widget metadata for ``path`` considering lock/high-confidence state."""

    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    metadata: Mapping[str, Any]
    if isinstance(raw_metadata, Mapping):
        metadata = raw_metadata
    else:  # pragma: no cover - defensive branch
        metadata = {}

    locked_fields = set(metadata.get("locked_fields") or [])
    high_conf_fields = set(metadata.get("high_confidence_fields") or [])
    confidence_map = _ensure_mapping(metadata.get("field_confidence"))
    confidence_entry = confidence_map.get(path)
    confidence_tier = ""
    confidence_icon = ""
    confidence_message = ""
    confidence_source = ""
    if isinstance(confidence_entry, Mapping):
        tier_value = confidence_entry.get("tier")
        if isinstance(tier_value, str):
            confidence_tier = tier_value
            (
                confidence_icon,
                confidence_message,
                confidence_source,
            ) = _confidence_indicator(confidence_tier)

    is_locked = path in locked_fields
    is_high_conf = path in high_conf_fields or (
        confidence_tier == ConfidenceTier.RULE_STRONG.value
    )
    was_locked = is_locked or is_high_conf

    source_info = _resolve_field_source_info(path)

    icons: list[str] = []
    if confidence_icon:
        icons.append(confidence_icon)
    if is_locked:
        icons.append("🔒")
    icon_prefix = " ".join(filter(None, icons))
    label_with_icon = f"{icon_prefix} {label}".strip() if icon_prefix else label

    help_bits: list[str] = []
    if confidence_message:
        help_bits.append(confidence_message)
    if is_locked:
        help_bits.append(
            tr(
                "Automatisch gesperrt – zum Bearbeiten zuerst entsperren.",
                "Locked automatically – unlock before editing.",
            )
        )
    help_text = " ".join(help_bits)

    config: FieldLockConfig = {"label": label_with_icon, "was_locked": was_locked}
    if confidence_tier:
        config["confidence_tier"] = confidence_tier
    if confidence_icon:
        config["confidence_icon"] = confidence_icon
    if confidence_message:
        config["confidence_message"] = confidence_message
    if confidence_source:
        config["confidence_source"] = confidence_source
    if help_text:
        config["help_text"] = help_text

    if not was_locked:
        config["unlocked"] = True
        return config

    container = container or st
    unlock_key = _field_unlock_key(path, context)
    unlocked_default = bool(st.session_state.get(unlock_key, False))
    unlocked = container.toggle(
        tr("Wert bearbeiten", "Edit value"),
        value=unlocked_default,
        key=unlock_key,
        help=help_text or None,
    )
    config["unlocked"] = bool(unlocked)
    if not unlocked:
        config["disabled"] = True
    return config


def _clear_field_unlock_state(path: str) -> None:
    """Remove stored unlock toggles for ``path`` across contexts."""

    normalized = path.replace(".", "_")
    prefix = f"{_FIELD_LOCK_BASE_KEY}."
    keys_to_remove = [
        key
        for key in list(st.session_state.keys())
        if isinstance(key, str)
        and key.startswith(prefix)
        and key.split(".")[-1] == normalized
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


def _remove_field_lock_metadata(path: str) -> None:
    """Drop lock/high-confidence metadata for ``path`` once the value changes."""

    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    if not isinstance(raw_metadata, Mapping):  # pragma: no cover - defensive guard
        return
    metadata = dict(raw_metadata)
    changed = False
    for key in ("locked_fields", "high_confidence_fields"):
        values = metadata.get(key)
        if isinstance(values, list) and path in values:
            metadata[key] = [item for item in values if item != path]
            changed = True
    confidence_map = metadata.get("field_confidence")
    if isinstance(confidence_map, Mapping) and path in confidence_map:
        updated = dict(confidence_map)
        if updated.pop(path, None) is not None:
            metadata["field_confidence"] = updated
            changed = True
    if changed:
        st.session_state[StateKeys.PROFILE_METADATA] = metadata
        _clear_field_unlock_state(path)


def _update_profile(path: str, value) -> None:
    """Update profile data and clear derived outputs if changed."""

    data = _get_profile_state()
    value = _normalize_value_for_path(path, value)
    current = get_in(data, path)
    if _normalize_semantic_empty(current) != _normalize_semantic_empty(value):
        set_in(data, path, value)
        _clear_generated()
        _remove_field_lock_metadata(path)


def _normalize_autofill_value(value: str | None) -> str:
    """Normalize ``value`` for comparison in autofill tracking."""

    if not value:
        return ""
    normalized = " ".join(value.strip().split()).casefold()
    return normalized


def _load_autofill_decisions() -> dict[str, list[str]]:
    """Return a copy of stored autofill rejection decisions."""

    raw = st.session_state.get(StateKeys.AUTOFILL_DECISIONS)
    if not isinstance(raw, Mapping):
        return {}
    decisions: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, list):
            items = [str(item) for item in value if isinstance(item, str)]
            decisions[key] = items
    return decisions


def _store_autofill_decisions(decisions: Mapping[str, list[str]]) -> None:
    """Persist ``decisions`` to session state."""

    st.session_state[StateKeys.AUTOFILL_DECISIONS] = {
        key: list(value) for key, value in decisions.items()
    }


def _autofill_was_rejected(field_path: str, suggestion: str) -> bool:
    """Return ``True`` when ``suggestion`` was rejected for ``field_path``."""

    normalized = _normalize_autofill_value(suggestion)
    if not normalized:
        return False
    decisions = _load_autofill_decisions()
    rejected = decisions.get(field_path, [])
    return normalized in rejected


def _record_autofill_rejection(field_path: str, suggestion: str) -> None:
    """Remember that ``suggestion`` was rejected for ``field_path``."""

    normalized = _normalize_autofill_value(suggestion)
    if not normalized:
        return
    decisions = _load_autofill_decisions()
    current = set(decisions.get(field_path, []))
    if normalized in current:
        return
    current.add(normalized)
    decisions[field_path] = sorted(current)
    _store_autofill_decisions(decisions)


def _render_autofill_suggestion(
    *,
    field_path: str,
    suggestion: str,
    title: str,
    description: str,
    widget_key: str | None = None,
    icon: str = "✨",
    success_message: str | None = None,
    rejection_message: str | None = None,
    success_icon: str = "✅",
    rejection_icon: str = "🗑️",
) -> None:
    """Render an optional autofill prompt for ``suggestion``."""

    suggestion = suggestion.strip()
    if not suggestion:
        return

    accept_label = f"{icon} {suggestion}" if icon else suggestion
    reject_label = tr("Ignorieren", "Dismiss")
    success_message = success_message or tr(
        "Vorschlag übernommen.", "Suggestion applied."
    )
    rejection_message = rejection_message or tr(
        "Vorschlag verworfen.", "Suggestion dismissed."
    )

    suggestion_hash = hashlib.sha1(
        f"{field_path}:{suggestion}".encode("utf-8")
    ).hexdigest()[:10]

    with st.container(border=True):
        st.markdown(f"**{title}**")
        if description:
            st.caption(description)
        st.markdown(f"`{suggestion}`")
        accept_col, reject_col = st.columns((1.4, 1))
        if accept_col.button(
            accept_label,
            key=f"autofill.accept.{field_path}.{suggestion_hash}",
            type="primary",
        ):
            if widget_key:
                st.session_state[widget_key] = suggestion
            _update_profile(field_path, suggestion)
            st.toast(success_message, icon=success_icon)
            st.rerun()
        if reject_col.button(
            reject_label,
            key=f"autofill.reject.{field_path}.{suggestion_hash}",
        ):
            _record_autofill_rejection(field_path, suggestion)
            st.toast(rejection_message, icon=rejection_icon)
            st.rerun()
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


def _collect_combined_certificates(requirements: Mapping[str, Any]) -> list[str]:
    """Return combined certificate entries across legacy keys."""

    raw_values: list[str] = []
    if isinstance(requirements, Mapping):
        for key in ("certificates", "certifications"):
            items = requirements.get(key, [])
            if isinstance(items, Sequence) and not isinstance(
                items, (str, bytes, bytearray)
            ):
                raw_values.extend(str(item) for item in items)
    return _unique_normalized(raw_values)


def _set_requirement_certificates(requirements: dict[str, Any], values: Iterable[str]) -> None:
    """Synchronize certificate lists under both legacy keys."""

    normalized = _unique_normalized(list(values))
    requirements["certificates"] = normalized
    requirements["certifications"] = list(normalized)


BOOLEAN_WIDGET_KEYS = "ui.summary.boolean_widget_keys"
BOOLEAN_PROFILE_SIGNATURE = "ui.summary.boolean_profile_signature"


def _boolean_skill_terms(profile: NeedAnalysisProfile) -> list[str]:
    """Collect deduplicated skills for the Boolean builder."""

    combined = (
        profile.requirements.hard_skills_required
        + profile.requirements.hard_skills_optional
        + profile.requirements.soft_skills_required
        + profile.requirements.soft_skills_optional
        + profile.requirements.tools_and_technologies
    )
    return _unique_normalized(combined)


def _boolean_title_synonyms(profile: NeedAnalysisProfile) -> list[str]:
    """Return potential job title synonyms for Boolean search."""

    job_title = (profile.position.job_title or "").strip()
    metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    synonyms: list[str] = []
    stored_synonyms = metadata.get("title_synonyms")
    if isinstance(stored_synonyms, list):
        synonyms.extend(str(item) for item in stored_synonyms)
    occupation_label = getattr(profile.position, "occupation_label", None)
    if occupation_label:
        cleaned = str(occupation_label).strip()
        if cleaned and cleaned.casefold() != job_title.casefold():
            synonyms.append(cleaned)
    return _unique_normalized(synonyms)


def _boolean_profile_signature(profile: NeedAnalysisProfile) -> str:
    """Return a stable fingerprint for the profile used by the Boolean UI."""

    payload = profile.model_dump()
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def _boolean_widget_key(prefix: str, value: str) -> str:
    """Generate a stable widget key for Boolean builder controls."""

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return f"{prefix}.{digest}"


def _render_boolean_download_button(
    *,
    boolean_query: str,
    job_title_value: str,
    key: str = "download_boolean",
) -> None:
    """Render the download button for Boolean strings."""

    download_label = tr(
        "⬇️ Boolean-String herunterladen",
        "⬇️ Download Boolean string",
    )
    safe_title = job_title_value or "boolean-search"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", safe_title).strip("-")
    safe_stem = safe_stem or "boolean-search"
    st.download_button(
        download_label,
        boolean_query or "",
        file_name=f"{safe_stem}.txt",
        mime="text/plain",
        key=key,
        disabled=not bool(boolean_query),
    )


def _render_boolean_interactive_section(
    profile: NeedAnalysisProfile,
    *,
    boolean_skill_terms: Sequence[str],
    boolean_title_synonyms: Sequence[str],
    download_key: str = "download_boolean",
) -> None:
    """Render the interactive Boolean UI shared across views."""

    st.markdown(tr("#### Boolean-Suche", "#### Boolean search"))
    st.caption(
        tr(
            "Stellen Sie den Suchstring aus Jobtitel, Synonymen und Skills zusammen.",
            "Assemble the search string from the job title, synonyms, and skills.",
        )
    )

    registry_keys: list[str] = []
    job_title_value = (profile.position.job_title or "").strip()
    synonyms = list(boolean_title_synonyms)
    include_title_default = bool(job_title_value or synonyms)
    include_title = False
    title_key = ""
    selected_synonyms: list[str] = []
    selected_skills: list[str] = []
    with st.expander(tr("Skills & Keywords", "Skills & keywords"), expanded=True):
        if include_title_default:
            key_basis = job_title_value or "|".join(synonyms) or "title"
            title_key = _boolean_widget_key("boolean.title", key_basis)
            include_title = st.checkbox(
                tr("Jobtitel einbeziehen", "Include job title"),
                value=st.session_state.get(title_key, True),
                key=title_key,
            )
            registry_keys.append(title_key)
            if job_title_value:
                st.caption(f'"{job_title_value}"')
        else:
            include_title = False

        if boolean_skill_terms:
            for skill in boolean_skill_terms:
                skill_key = _boolean_widget_key("boolean.skill", skill)
                checked = st.checkbox(
                    skill,
                    value=st.session_state.get(skill_key, True),
                    key=skill_key,
                )
                if checked:
                    selected_skills.append(skill)
                registry_keys.append(skill_key)
        else:
            st.caption(tr("Noch keine Skills erfasst.", "No skills captured yet."))

    if synonyms:
        with st.expander(tr("Titel-Synonyme", "Title synonyms"), expanded=True):
            for synonym in synonyms:
                syn_key = _boolean_widget_key("boolean.synonym", synonym)
                checked = st.checkbox(
                    f'"{synonym}"',
                    value=st.session_state.get(syn_key, True),
                    key=syn_key,
                    disabled=not include_title,
                )
                if include_title and checked:
                    selected_synonyms.append(synonym)
                registry_keys.append(syn_key)

    include_title_clause = include_title and bool(job_title_value or selected_synonyms)
    boolean_query = ""
    if include_title_clause or selected_skills:
        boolean_query = build_boolean_query(
            job_title_value,
            selected_skills,
            include_title=include_title_clause,
            title_synonyms=selected_synonyms if selected_synonyms else None,
        )
    st.session_state[StateKeys.BOOLEAN_STR] = boolean_query

    if boolean_query:
        st.code(boolean_query, language=None)
    else:
        st.info(
            tr(
                "Bitte mindestens einen Begriff auswählen, um die Suche zu erzeugen.",
                "Select at least one term to build the search.",
            )
        )

    _render_boolean_download_button(
        boolean_query=boolean_query,
        job_title_value=job_title_value,
        key=download_key,
    )

    st.session_state[BOOLEAN_WIDGET_KEYS] = sorted(set(registry_keys))


def render_boolean_builder(profile: NeedAnalysisProfile) -> None:
    """Render the interactive Boolean builder based on the profile."""

    default_boolean_query = build_boolean_search(profile)
    profile_signature = _boolean_profile_signature(profile)
    stored_signature = st.session_state.get(BOOLEAN_PROFILE_SIGNATURE)
    if stored_signature != profile_signature:
        for widget_key in list(st.session_state.get(BOOLEAN_WIDGET_KEYS, [])):
            st.session_state.pop(widget_key, None)
        st.session_state[BOOLEAN_WIDGET_KEYS] = []
        st.session_state[BOOLEAN_PROFILE_SIGNATURE] = profile_signature
        st.session_state[StateKeys.BOOLEAN_STR] = default_boolean_query
    elif StateKeys.BOOLEAN_STR not in st.session_state:
        st.session_state[StateKeys.BOOLEAN_STR] = default_boolean_query

    boolean_skill_terms = _boolean_skill_terms(profile)
    boolean_title_synonyms = _boolean_title_synonyms(profile)

    _render_boolean_interactive_section(
        profile,
        boolean_skill_terms=boolean_skill_terms,
        boolean_title_synonyms=boolean_title_synonyms,
    )


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
def _chip_multiselect(
    label: str,
    options: List[str],
    values: List[str],
    *,
    help_text: str | None = None,
    dropdown: bool = False,
) -> List[str]:
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
    last_added_key = f"ui.chip_last_added.{slug}"

    base_options = _unique_normalized(options)
    base_values = _unique_normalized(values)

    current_selection = _unique_normalized(st.session_state.get(ms_key, []))
    if current_selection:
        base_values = current_selection

    stored_options = _unique_normalized(st.session_state.get(options_key, []))
    available_options = _unique_normalized(stored_options + base_options + base_values)
    available_options = sorted(available_options, key=str.casefold)
    st.session_state[options_key] = available_options

    def _add_chip_entry() -> None:
        raw_value = st.session_state.get(input_key, "")
        candidate = raw_value.strip() if isinstance(raw_value, str) else ""

        if not candidate:
            st.session_state[input_key] = ""
            st.session_state[last_added_key] = ""
            return

        last_added = st.session_state.get(last_added_key, "")
        current_values = _unique_normalized(st.session_state.get(ms_key, base_values))
        current_markers = {item.casefold() for item in current_values}
        candidate_marker = candidate.casefold()

        if (
            candidate_marker in current_markers
            and candidate_marker == str(last_added).casefold()
        ):
            st.session_state[input_key] = ""
            return

        updated_options = sorted(
            _unique_normalized(st.session_state.get(options_key, []) + [candidate]),
            key=str.casefold,
        )
        updated_values = _unique_normalized(current_values + [candidate])

        st.session_state[options_key] = updated_options
        st.session_state[ms_key] = updated_values
        st.session_state[last_added_key] = candidate
        st.session_state[input_key] = ""

    container = st.expander(label, expanded=True) if dropdown else st.container()
    with container:
        if dropdown and help_text:
            st.caption(help_text)
        st.text_input(
            tr("Neuen Wert hinzufügen", "Add new value"),
            key=input_key,
            placeholder=tr("Neuen Wert hinzufügen …", "Add new value …"),
            label_visibility="collapsed",
            on_change=_add_chip_entry,
        )

        default_selection = _unique_normalized(
            st.session_state.get(ms_key, base_values)
        )
        selection = st.multiselect(
            label if not dropdown else tr("Auswahl", "Selection"),
            options=available_options,
            default=default_selection,
            key=ms_key,
            help=None if dropdown else help_text,
            label_visibility="visible" if not dropdown else "collapsed",
        )
    return _unique_normalized(selection)


# --- Step-Renderers ---
def _step_onboarding(schema: dict) -> None:
    """Render onboarding with language toggle, intro, and ingestion options."""

    _maybe_run_extraction(schema)

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)

    welcome_headline = tr(
        "KI-gestützte Recruiting-Analyse mit Cognitive Needs",
        "AI-powered recruiting analysis with Cognitive Needs",
    )
    welcome_text = tr(
        "Sammle zu Beginn ALLE Recruiting-relevanten Daten und spare Nerven, Zeit und Kosten",
        "Collect all recruiting-relevant data from the start and save nerves, time, and costs",
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
    onboarding_header = _format_dynamic_message(
        default=("Anzeige parat?", "Job ad ready?"),
        context=profile_context,
        variants=[
            (
                (
                    "Anzeige für {job_title} bei {company_name} parat?",
                    "Job ad for {job_title} at {company_name} ready?",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Anzeige für {job_title} parat?",
                    "Job ad for {job_title} ready?",
                ),
                ("job_title",),
            ),
        ],
    )
    st.subheader(onboarding_header)
    onboarding_caption = _format_dynamic_message(
        default=(
            "Gebe ein paar Informationen zu Deiner Vakanz und starte die dynamisch angepasste Analyse",
            "Share a few details about your vacancy and start the dynamically tailored analysis",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Teile kurz die Eckdaten zu {job_title} bei {company_name} und starte die dynamisch angepasste Analyse.",
                    "Share the key details for {job_title} at {company_name} to kick off the tailored analysis.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Teile kurz die Eckdaten zur Rolle {job_title} und starte die dynamisch angepasste Analyse.",
                    "Share the key details for the {job_title} role to kick off the tailored analysis.",
                ),
                ("job_title",),
            ),
        ],
    )
    st.caption(onboarding_caption)

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
        doc_prefill = st.session_state.get("__prefill_profile_doc__")
        if doc_prefill:
            st.session_state[StateKeys.RAW_BLOCKS] = doc_prefill.blocks

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
            _request_scroll_to_top()
            st.session_state[StateKeys.STEP] = COMPANY_STEP_INDEX
            st.rerun()


def _step_company():
    """Render the company information step.

    Returns:
        None
    """

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
    st.subheader(company_header)
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
    st.caption(company_caption)
    data = profile
    combined_certificates = _collect_combined_certificates(data["requirements"])
    _set_requirement_certificates(data["requirements"], combined_certificates)
    missing_here = _missing_fields_for_section(1)

    data["company"]["website"] = st.text_input(
        tr("Website", "Website"),
        value=data["company"].get("website", ""),
        placeholder="https://example.com",
        key="ui.company.website",
    )
    data["company"]["mission"] = st.text_input(
        tr("Mission", "Mission"),
        value=data["company"].get("mission", ""),
        placeholder=tr(
            "z. B. Nachhaltige Mobilität fördern",
            "e.g., Promote sustainable mobility",
        ),
        key="ui.company.mission",
    )
    data["company"]["culture"] = st.text_input(
        tr("Unternehmenskultur", "Company culture"),
        value=data["company"].get("culture", ""),
        placeholder=tr(
            "z. B. Teamorientiert, innovationsgetrieben",
            "e.g., Team-oriented, innovation-driven",
        ),
        key="ui.company.culture",
    )

    _render_company_research_tools(data["company"].get("website", ""))

    label_company = tr("Firma", "Company")
    if "company.name" in missing_here:
        label_company += REQUIRED_SUFFIX
    company_lock = _field_lock_config(
        "company.name",
        label_company,
        container=st,
        context="step",
    )
    company_kwargs = _apply_field_lock_kwargs(
        company_lock,
        {"help": tr("Offizieller Firmenname", "Official company name")},
    )
    data["company"]["name"] = st.text_input(
        company_lock["label"],
        value=data["company"].get("name", ""),
        placeholder=tr("z. B. ACME GmbH", "e.g., ACME Corp"),
        **company_kwargs,
    )
    _update_profile("company.name", data["company"]["name"])
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
        key=UIKeys.COMPANY_HQ_LOCATION,
    )
    data["company"]["size"] = c4.text_input(
        tr("Größe", "Size"),
        value=data["company"].get("size", ""),
        placeholder=tr("z. B. 50-100", "e.g., 50-100"),
    )

    contact_cols = st.columns(3)
    data["company"]["contact_name"] = contact_cols[0].text_input(
        tr("Ansprechperson", "Primary contact"),
        value=data["company"].get("contact_name", ""),
        placeholder=tr("z. B. Maria Beispiel", "e.g., Maria Example"),
        key=UIKeys.COMPANY_CONTACT_NAME,
    )
    data["company"]["contact_email"] = contact_cols[1].text_input(
        tr("Kontakt E-Mail", "Contact email"),
        value=data["company"].get("contact_email", ""),
        placeholder="contact@example.com",
    )
    data["company"]["contact_phone"] = contact_cols[2].text_input(
        tr("Kontakt Telefon", "Contact phone"),
        value=data["company"].get("contact_phone", ""),
        placeholder=tr("z. B. +49 30 123456", "e.g., +49 30 123456"),
    )

    contact_email_value = (data["company"].get("contact_email") or "").strip()
    contact_name_value = (data["company"].get("contact_name") or "").strip()
    inferred_contact_name = infer_contact_name_from_email(contact_email_value)
    if (
        inferred_contact_name
        and not contact_name_value
        and not _autofill_was_rejected("company.contact_name", inferred_contact_name)
    ):
        _render_autofill_suggestion(
            field_path="company.contact_name",
            suggestion=inferred_contact_name,
            title=tr("👤 Kontakt übernehmen?", "👤 Use inferred contact?"),
            description=tr(
                "Aus der E-Mail-Adresse abgeleiteter Name.",
                "Name inferred from the email address.",
            ),
            widget_key=UIKeys.COMPANY_CONTACT_NAME,
            icon="👤",
            success_message=tr(
                "Kontaktname aus E-Mail übernommen.",
                "Contact name copied from email.",
            ),
            rejection_message=tr(
                "Vorschlag ignoriert – wir merken uns das.",
                "Suggestion dismissed – we'll remember that.",
            ),
        )

    # Inline follow-up questions for Company section
    _render_followups_for_section(("company.",), data)


_step_company.handled_fields = [  # type: ignore[attr-defined]
    "company.name",
    "company.brand_name",
    "company.industry",
    "company.hq_location",
    "company.size",
    "company.website",
    "company.mission",
    "company.culture",
    "company.contact_name",
    "company.contact_email",
    "company.contact_phone",
]


def _phase_display_labels(phases: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return display labels for ``phases`` preserving order."""

    labels: list[str] = []
    for index, phase in enumerate(phases):
        name = ""
        if isinstance(phase, Mapping):
            raw = phase.get("name", "")
            if isinstance(raw, str):
                name = raw.strip()
        labels.append(name or f"{tr('Phase', 'Phase')} {index + 1}")
    return labels


def _phase_label_formatter(labels: Sequence[str]) -> Callable[[int], str]:
    """Return a formatter for phase indices used in multi-select widgets."""

    def _format(index: int) -> str:
        if 0 <= index < len(labels):
            return labels[index]
        return f"{tr('Phase', 'Phase')} {index + 1}"

    return _format


def _filter_phase_indices(selected: Sequence[Any], total: int) -> list[int]:
    """Clean phase indices ensuring they are within ``total``."""

    cleaned: list[int] = []
    seen: set[int] = set()
    for value in selected:
        candidate: int | None = None
        if isinstance(value, int):
            candidate = value
        elif isinstance(value, str) and value.isdigit():
            candidate = int(value)
        if candidate is None or candidate in seen:
            continue
        if 0 <= candidate < total:
            cleaned.append(candidate)
            seen.add(candidate)
    return cleaned


def _parse_timeline_range(value: str | None) -> tuple[date | None, date | None]:
    """Extract ISO date range from ``value`` if present."""

    if not value:
        return (None, None)
    matches = re.findall(r"(\d{4}-\d{2}-\d{2})", value)
    if not matches:
        return (None, None)
    try:
        start = date.fromisoformat(matches[0])
    except ValueError:
        start = None
    end: date | None
    if len(matches) >= 2:
        try:
            end = date.fromisoformat(matches[1])
        except ValueError:
            end = None
    else:
        end = start
    return (start, end)


def _timeline_default_range(value: str | None) -> tuple[date, date]:
    """Return default start/end dates for the recruitment timeline widget."""

    start, end = _parse_timeline_range(value)
    today = date.today()
    start = start or today
    end = end or start
    if end < start:
        start, end = end, start
    return start, end


def _default_date(value: Any, *, fallback: date | None = None) -> date:
    """Return a ``date`` for widgets, parsing ISO strings when possible."""

    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return date.today()


def _normalize_date_selection(value: Any) -> tuple[date | None, date | None]:
    """Normalize ``st.date_input`` return value to a ``(start, end)`` tuple."""

    if isinstance(value, date):
        return value, value
    if isinstance(value, (list, tuple)):
        dates = [item for item in value if isinstance(item, date)]
        if len(dates) >= 2:
            return dates[0], dates[1]
        if dates:
            return dates[0], dates[0]
    return (None, None)


def _format_timeline_string(start: date | None, end: date | None) -> str:
    """Format ``start`` and ``end`` dates into a persisted string."""

    if not start:
        return ""
    end = end or start
    if end < start:
        start, end = end, start
    if end == start:
        return start.isoformat()
    return f"{start.isoformat()} – {end.isoformat()}"


def _split_onboarding_entries(value: Any) -> list[str]:
    """Return onboarding entries from stored value as a clean list."""

    if isinstance(value, str):
        items = [line.strip() for line in value.splitlines() if line.strip()]
        return items
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [str(item).strip() for item in value if str(item).strip()]
        seen: set[str] = set()
        deduped: list[str] = []
        for entry in items:
            low = entry.lower()
            if low in seen:
                continue
            seen.add(low)
            deduped.append(entry)
        return deduped
    return []


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
    phase_labels = _phase_display_labels(process.get("phases", []))
    phase_indices = list(range(len(phase_labels)))
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

        existing_selection = _filter_phase_indices(
            person.get("information_loop_phases", []), len(phase_indices)
        )
        if existing_selection != person.get("information_loop_phases"):
            person["information_loop_phases"] = existing_selection
        person["information_loop_phases"] = st.multiselect(
            tr("Informationsloop-Phasen", "Information loop phases"),
            options=phase_indices,
            default=existing_selection,
            format_func=_phase_label_formatter(phase_labels),
            key=f"{key_prefix}.{idx}.loop",
            help=tr(
                "Wähle die Phasen, in denen dieser Kontakt informiert wird.",
                "Select the process phases where this contact stays in the loop.",
            ),
            disabled=not phase_indices,
        )
        if not phase_indices:
            st.caption(
                tr(
                    "Füge unten Phasen hinzu, um Kontakte dem Informationsloop zuzuordnen.",
                    "Add process phases below to assign contacts to the information loop.",
                )
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
        with st.expander(f"{tr('Phase', 'Phase')} {idx + 1}", expanded=False):
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


def _render_onboarding_section(
    process: dict, key_prefix: str, *, allow_generate: bool = True
) -> None:
    """Render onboarding suggestions with optional LLM generation."""

    lang = st.session_state.get("lang", "de")
    profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
    existing_entries = _split_onboarding_entries(process.get("onboarding_process", ""))

    job_title_state_value = st.session_state.get("position.job_title", "")
    job_title = str(job_title_state_value or "").strip()
    if not job_title and isinstance(profile, Mapping):
        job_title = str((profile.get("position") or {}).get("job_title") or "").strip()

    if allow_generate:
        if not job_title:
            st.info(
                tr(
                    "Bitte gib einen Jobtitel ein, um Onboarding-Vorschläge zu erstellen.",
                    "Please provide a job title to generate onboarding suggestions.",
                )
            )
        generate_clicked = st.button(
            "🤖 "
            + tr("Onboarding-Vorschläge generieren", "Generate onboarding suggestions"),
            key=f"{key_prefix}.generate",
            disabled=not job_title,
        )
        if generate_clicked and job_title:
            company_data = (
                profile.get("company") if isinstance(profile, Mapping) else {}
            )
            company_name = ""
            industry = ""
            culture = ""
            if isinstance(company_data, Mapping):
                company_name = str(company_data.get("name") or "").strip()
                industry = str(company_data.get("industry") or "").strip()
                culture = str(company_data.get("culture") or "").strip()
            suggestions, err = get_onboarding_suggestions(
                job_title,
                company_name=company_name,
                industry=industry,
                culture=culture,
                lang=lang,
            )
            if err or not suggestions:
                st.warning(
                    tr(
                        "Onboarding-Vorschläge nicht verfügbar (API-Fehler)",
                        "Onboarding suggestions not available (API error)",
                    )
                )
                if err and st.session_state.get("debug"):
                    st.session_state["onboarding_suggestions_error"] = err
            else:
                st.session_state[StateKeys.ONBOARDING_SUGGESTIONS] = suggestions
                st.rerun()

    current_suggestions = (
        st.session_state.get(StateKeys.ONBOARDING_SUGGESTIONS, []) or []
    )
    options = list(dict.fromkeys(current_suggestions + existing_entries))
    defaults = [opt for opt in options if opt in existing_entries]
    selected = st.multiselect(
        tr("Onboarding-Prozess", "Onboarding process"),
        options=options,
        default=defaults,
        key=f"{key_prefix}.selection",
        help=tr(
            "Wähle die Vorschläge aus, die in den Onboarding-Prozess übernommen werden sollen.",
            "Select the suggestions you want to include in the onboarding process.",
        ),
        placeholder=tr(
            "Vorschläge auswählen oder generieren", "Select or generate suggestions"
        ),
    )
    if not options:
        st.info(
            tr(
                "Klicke auf den Button, um passende Onboarding-Vorschläge zu erstellen.",
                "Click the button to generate tailored onboarding suggestions.",
            )
        )

    cleaned = [item.strip() for item in selected if item.strip()]
    process["onboarding_process"] = "\n".join(cleaned)


def _step_position():
    """Render the position details step.",

    Returns:
        None
    """

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)
    position_header = _format_dynamic_message(
        default=("Basisdaten", "Basic data"),
        context=profile_context,
        variants=[
            (
                (
                    "{job_title} bei {company_name}",
                    "{job_title} at {company_name}",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "{job_title} in {location_combined}",
                    "{job_title} in {location_combined}",
                ),
                ("job_title", "location_combined"),
            ),
            (
                (
                    "Rolle: {job_title}",
                    "Role: {job_title}",
                ),
                ("job_title",),
            ),
        ],
    )
    st.subheader(position_header)
    position_caption = _format_dynamic_message(
        default=(
            "Kerninformationen zur Rolle, zum Standort und Rahmenbedingungen erfassen.",
            "Capture key information about the role, location and context.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Kerninformationen zur Rolle {job_title} bei {company_name} festhalten.",
                    "Capture the key information for {job_title} at {company_name}.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Kerninformationen zur Rolle {job_title} in {location_combined} festhalten.",
                    "Capture the key information for {job_title} in {location_combined}.",
                ),
                ("job_title", "location_combined"),
            ),
            (
                (
                    "Kerninformationen zur Rolle {job_title} festhalten.",
                    "Capture the key information for the {job_title} role.",
                ),
                ("job_title",),
            ),
        ],
    )
    st.caption(position_caption)
    data = profile
    company = data.setdefault("company", {})
    position = data.setdefault("position", {})
    location_data = data.setdefault("location", {})
    meta_data = data.setdefault("meta", {})
    employment = data.setdefault("employment", {})

    missing_here = _missing_fields_for_section(2)

    st.markdown("#### " + tr("Rolle & Team", "Role & team"))
    role_cols = st.columns((1.3, 1))
    title_label = tr("Jobtitel", "Job title")
    if "position.job_title" in missing_here:
        title_label += REQUIRED_SUFFIX
    title_lock = _field_lock_config(
        "position.job_title",
        title_label,
        container=role_cols[0],
        context="step",
    )
    job_title_kwargs = _apply_field_lock_kwargs(title_lock)
    position["job_title"] = role_cols[0].text_input(
        title_lock["label"],
        value=position.get("job_title", ""),
        placeholder=tr("z. B. Data Scientist", "e.g., Data Scientist"),
        **job_title_kwargs,
    )
    _update_profile("position.job_title", position["job_title"])
    if "position.job_title" in missing_here and not position.get("job_title"):
        role_cols[0].caption(
            tr("Dieses Feld ist erforderlich", "This field is required")
        )

    position["seniority_level"] = role_cols[1].text_input(
        tr("Seniorität", "Seniority"),
        value=position.get("seniority_level", ""),
        placeholder=tr("z. B. Junior", "e.g., Junior"),
    )

    dept_cols = st.columns(2)
    position["department"] = dept_cols[0].text_input(
        tr("Abteilung", "Department"),
        value=position.get("department", ""),
        placeholder=tr("z. B. Entwicklung", "e.g., Engineering"),
    )
    position["team_structure"] = dept_cols[1].text_input(
        tr("Teamstruktur", "Team structure"),
        value=position.get("team_structure", ""),
        placeholder=tr(
            "z. B. 5 Personen, cross-funktional", "e.g., 5 people, cross-functional"
        ),
    )

    summary_cols = st.columns((1, 1))
    position["reporting_line"] = summary_cols[0].text_input(
        tr("Reports an", "Reports to"),
        value=position.get("reporting_line", ""),
        placeholder=tr("z. B. CTO", "e.g., CTO"),
    )
    summary_label = tr("Rollen-Summary", "Role summary")
    if "position.role_summary" in missing_here:
        summary_label += REQUIRED_SUFFIX
    position["role_summary"] = summary_cols[1].text_area(
        summary_label,
        value=position.get("role_summary", ""),
        height=120,
    )
    if "position.role_summary" in missing_here and not position.get("role_summary"):
        summary_cols[1].caption(
            tr("Dieses Feld ist erforderlich", "This field is required")
        )

    st.markdown("#### " + tr("Standort & Zeitplan", "Location & timing"))
    location_cols = st.columns(2)
    city_lock = _field_lock_config(
        "location.primary_city",
        tr("Stadt", "City"),
        container=location_cols[0],
        context="step",
    )
    city_kwargs = _apply_field_lock_kwargs(city_lock)
    location_data["primary_city"] = location_cols[0].text_input(
        city_lock["label"],
        value=location_data.get("primary_city", ""),
        placeholder=tr("z. B. Berlin", "e.g., Berlin"),
        **city_kwargs,
    )
    _update_profile("location.primary_city", location_data["primary_city"])
    country_label = tr("Land", "Country")
    if "location.country" in missing_here:
        country_label += REQUIRED_SUFFIX
    country_lock = _field_lock_config(
        "location.country",
        country_label,
        container=location_cols[1],
        context="step",
    )
    country_kwargs = _apply_field_lock_kwargs(country_lock)
    location_data["country"] = location_cols[1].text_input(
        country_lock["label"],
        value=location_data.get("country", ""),
        placeholder=tr("z. B. DE", "e.g., DE"),
        **country_kwargs,
    )
    _update_profile("location.country", location_data["country"])
    if "location.country" in missing_here and not location_data.get("country"):
        location_cols[1].caption(
            tr("Dieses Feld ist erforderlich", "This field is required")
        )

    city_value = (location_data.get("primary_city") or "").strip()
    country_value = (location_data.get("country") or "").strip()
    hq_value = (company.get("hq_location") or "").strip()
    suggested_hq_parts = [part for part in (city_value, country_value) if part]
    suggested_hq = ", ".join(suggested_hq_parts)
    if (
        suggested_hq
        and not hq_value
        and not _autofill_was_rejected("company.hq_location", suggested_hq)
    ):
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
            field_path="company.hq_location",
            suggestion=suggested_hq,
            title=tr("🏙️ Hauptsitz übernehmen?", "🏙️ Use this as headquarters?"),
            description=description,
            widget_key=UIKeys.COMPANY_HQ_LOCATION,
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

    timing_cols = st.columns(3)
    target_start_default = _default_date(meta_data.get("target_start_date"))
    start_selection = timing_cols[0].date_input(
        tr("Gewünschtes Startdatum", "Desired start date"),
        value=target_start_default,
        format="YYYY-MM-DD",
    )
    meta_data["target_start_date"] = (
        start_selection.isoformat() if isinstance(start_selection, date) else ""
    )

    application_deadline_default = _default_date(meta_data.get("application_deadline"))
    deadline_selection = timing_cols[1].date_input(
        tr("Bewerbungsschluss", "Application deadline"),
        value=application_deadline_default,
        format="YYYY-MM-DD",
    )
    meta_data["application_deadline"] = (
        deadline_selection.isoformat() if isinstance(deadline_selection, date) else ""
    )

    position["supervises"] = timing_cols[2].number_input(
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
        position["key_projects"] = st.text_area(
            tr("Schlüsselprojekte", "Key projects"),
            value=position.get("key_projects", ""),
            height=80,
        )

    st.markdown(
        "#### " + tr("Beschäftigung & Arbeitsmodell", "Employment & working model")
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
    contract_index = (
        contract_keys.index(contract_default)
        if contract_default in contract_keys
        else 0
    )
    employment["contract_type"] = job_cols[1].selectbox(
        tr("Vertragsform", "Contract type"),
        options=contract_keys,
        index=contract_index,
        format_func=lambda key: contract_options[key],
    )

    policy_keys = list(policy_options.keys())
    policy_default = employment.get("work_policy", policy_keys[0])
    policy_index = (
        policy_keys.index(policy_default) if policy_default in policy_keys else 0
    )
    employment["work_policy"] = job_cols[2].selectbox(
        tr("Arbeitsmodell", "Work model"),
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
    schedule_default = employment.get("work_schedule", schedule_keys[0])
    schedule_index = (
        schedule_keys.index(schedule_default)
        if schedule_default in schedule_keys
        else 0
    )
    schedule_cols = st.columns(3)
    employment["work_schedule"] = schedule_cols[0].selectbox(
        tr("Arbeitszeitmodell", "Work schedule"),
        options=schedule_keys,
        index=schedule_index,
        format_func=lambda key: schedule_options[key],
    )

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
        contract_end_default = _default_date(
            employment.get("contract_end"), fallback=date.today()
        )
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
    )
    employment["relocation_support"] = toggle_row_1[1].toggle(
        tr("Relocation?", "Relocation?"),
        value=bool(employment.get("relocation_support")),
    )
    employment["visa_sponsorship"] = toggle_row_1[2].toggle(
        tr("Visum-Sponsoring?", "Visa sponsorship?"),
        value=bool(employment.get("visa_sponsorship")),
    )

    toggle_row_2 = st.columns(3)
    employment["overtime_expected"] = toggle_row_2[0].toggle(
        tr("Überstunden?", "Overtime expected?"),
        value=bool(employment.get("overtime_expected")),
    )
    employment["security_clearance_required"] = toggle_row_2[1].toggle(
        tr("Sicherheitsüberprüfung?", "Security clearance required?"),
        value=bool(employment.get("security_clearance_required")),
    )
    employment["shift_work"] = toggle_row_2[2].toggle(
        tr("Schichtarbeit?", "Shift work?"),
        value=bool(employment.get("shift_work")),
    )

    if employment.get("travel_required"):
        with st.expander(
            tr("Details zur Reisetätigkeit", "Travel details"), expanded=True
        ):
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
            employment["travel_region_scope"] = selected_scope

            stored_regions = employment.get("travel_regions", [])
            stored_continents = employment.get("travel_continents", [])

            if selected_scope == "germany":
                selected_regions = col_region.multiselect(
                    tr("Bundesländer", "Federal states"),
                    options=GERMAN_STATES,
                    default=[
                        region for region in stored_regions if region in GERMAN_STATES
                    ],
                )
                employment["travel_regions"] = selected_regions
                employment.pop("travel_continents", None)
            elif selected_scope == "europe":
                selected_regions = col_region.multiselect(
                    tr("Länder (Europa)", "Countries (Europe)"),
                    options=EUROPEAN_COUNTRIES,
                    default=[
                        region
                        for region in stored_regions
                        if region in EUROPEAN_COUNTRIES
                    ],
                )
                employment["travel_regions"] = selected_regions
                employment.pop("travel_continents", None)
            else:
                continent_options = list(CONTINENT_COUNTRIES.keys())
                selected_continents = col_region.multiselect(
                    tr("Kontinente", "Continents"),
                    options=continent_options,
                    default=[
                        continent
                        for continent in stored_continents
                        if continent in continent_options
                    ],
                )
                employment["travel_continents"] = selected_continents
                base_continents = selected_continents or continent_options
                available_countries = sorted(
                    {
                        country
                        for continent in base_continents
                        for country in CONTINENT_COUNTRIES.get(continent, [])
                    }
                )
                selected_countries = col_region.multiselect(
                    tr("Länder", "Countries"),
                    options=available_countries,
                    default=[
                        country
                        for country in stored_regions
                        if country in available_countries
                    ],
                )
                employment["travel_regions"] = selected_countries

            employment["travel_details"] = col_details.text_input(
                tr("Zusatzinfos", "Additional details"),
                value=employment.get("travel_details", ""),
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
        employment["relocation_details"] = st.text_input(
            tr("Relocation-Details", "Relocation details"),
            value=employment.get("relocation_details", ""),
        )
    else:
        employment.pop("relocation_details", None)

    # Inline follow-up questions for Position, Location and Employment section
    _render_followups_for_section(
        ("position.", "location.", "meta.", "employment."), data
    )


_step_position.handled_fields = [  # type: ignore[attr-defined]
    "position.job_title",
    "position.role_summary",
    "location.country",
]



def _step_requirements():
    """Render the requirements step for skills and certifications."""

    data = _get_profile_state()
    missing_here = _missing_fields_for_section(3)

    requirements_style_key = "ui.requirements_styles"
    if not st.session_state.get(requirements_style_key):
        st.markdown(
            """
            <style>
            .requirement-panel {
                border-radius: 0.9rem;
                border: 1px solid rgba(148, 163, 184, 0.35);
                background: rgba(248, 250, 252, 0.85);
                padding: 1.25rem 1.4rem;
                margin-bottom: 1.2rem;
            }
            .requirement-panel__header {
                display: flex;
                gap: 0.5rem;
                align-items: center;
                font-weight: 600;
                font-size: 1.05rem;
            }
            .requirement-panel__caption {
                color: #475569;
                margin: 0.15rem 0 0.95rem 0;
                font-size: 0.92rem;
            }
            .requirement-panel__icon {
                font-size: 1.1rem;
            }
            .ai-suggestion-box {
                margin-top: 0.6rem;
                padding: 0.75rem 0.85rem;
                border-radius: 0.75rem;
                border: 1px dashed rgba(14, 165, 233, 0.6);
                background: rgba(14, 165, 233, 0.08);
            }
            .ai-suggestion-box__title {
                font-weight: 600;
                margin-bottom: 0.3rem;
            }
            .ai-suggestion-box__caption {
                font-size: 0.85rem;
                color: #0369a1;
                margin-bottom: 0.5rem;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state[requirements_style_key] = True

    # LLM-basierte Skill-Vorschläge abrufen
    job_title = (data.get("position", {}).get("job_title", "") or "").strip()
    lang = st.session_state.get("lang", "en")
    suggestions: dict[str, list[str]] = {}
    suggestions_error: str | None = None
    has_missing_key = bool(st.session_state.get("openai_api_key_missing"))
    suggestion_hint: str | None = None
    stored_suggestions = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {})
    if job_title and not has_missing_key:
        if (
            stored_suggestions.get("_title") == job_title
            and stored_suggestions.get("_lang") == lang
        ):
            suggestions = {
                key: stored_suggestions.get(key, [])
                for key in (
                    "hard_skills",
                    "soft_skills",
                    "tools_and_technologies",
                    "certificates",
                )
            }
        else:
            suggestions, suggestions_error = get_skill_suggestions(job_title, lang=lang)
            st.session_state[StateKeys.SKILL_SUGGESTIONS] = {
                "_title": job_title,
                "_lang": lang,
                **suggestions,
            }
    elif has_missing_key:
        suggestion_hint = "missing_key"
    else:
        suggestion_hint = "missing_title"

    if suggestions_error:
        st.warning(
            tr(
                "Skill-Vorschläge nicht verfügbar (API-Fehler)",
                "Skill suggestions not available (API error)",
            )
        )
        if st.session_state.get("debug"):
            st.session_state["skill_suggest_error"] = suggestions_error

    profile_context = _build_profile_context(data)
    requirements_header = _format_dynamic_message(
        default=("Anforderungen", "Requirements"),
        context=profile_context,
        variants=[
            (
                (
                    "Anforderungen für {job_title} bei {company_name}",
                    "Requirements for {job_title} at {company_name}",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Anforderungen für {job_title}",
                    "Requirements for {job_title}",
                ),
                ("job_title",),
            ),
        ],
    )
    st.subheader(requirements_header)
    requirements_caption = _format_dynamic_message(
        default=(
            "Geforderte Fähigkeiten und Qualifikationen festhalten.",
            "Specify required skills and qualifications.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Wichtige Fähigkeiten für {job_title} bei {company_name} sammeln.",
                    "Document the key skills for {job_title} at {company_name}.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Wichtige Fähigkeiten für {job_title} sammeln.",
                    "Document the key skills for {job_title}.",
                ),
                ("job_title",),
            ),
        ],
    )
    st.caption(requirements_caption)

    def _render_required_caption(condition: bool) -> None:
        if condition:
            st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    @contextmanager
    def requirement_panel(
        *,
        icon: str,
        title: str,
        caption: str,
        tooltip: str,
        parent: DeltaGenerator | None = None,
    ):
        if parent is not None:
            panel_container = parent.container()
        else:
            panel_container = st.container()
        panel_container.markdown(
            f"<div class='requirement-panel' title='{html.escape(tooltip)}'>",
            unsafe_allow_html=True,
        )
        panel_container.markdown(
            (
                "<div class='requirement-panel__header'>"
                f"<span class='requirement-panel__icon'>{icon}</span>"
                f"<span>{title}</span>"
                "</div>"
                f"<p class='requirement-panel__caption'>{caption}</p>"
            ),
            unsafe_allow_html=True,
        )
        body = panel_container.container()
        try:
            with body:
                yield
        finally:
            panel_container.markdown("</div>", unsafe_allow_html=True)

    def _render_ai_suggestions(
        *,
        source_key: str,
        target_key: str,
        widget_suffix: str,
        caption: str,
        show_hint: bool = False,
    ) -> None:
        if suggestion_hint == "missing_key":
            if show_hint:
                st.info(
                    tr(
                        "Skill-Vorschläge erfordern einen gültigen OpenAI API Key in den Einstellungen.",
                        "Skill suggestions require a valid OpenAI API key in the settings.",
                    )
                )
            return
        if suggestion_hint == "missing_title":
            if show_hint:
                st.info(
                    tr(
                        "Füge einen Jobtitel hinzu, um KI-Vorschläge zu erhalten.",
                        "Add a job title to unlock AI suggestions.",
                    )
                )
            return

        existing_terms: set[str] = set()
        for key_name in (
            "hard_skills_required",
            "hard_skills_optional",
            "soft_skills_required",
            "soft_skills_optional",
            "tools_and_technologies",
            "certificates",
        ):
            for entry in data["requirements"].get(key_name, []) or []:
                existing_terms.add(str(entry).casefold())

        normalized_pool: list[str] = []
        seen_terms: set[str] = set()
        for raw in suggestions.get(source_key, []):
            cleaned = str(raw or "").strip()
            if not cleaned:
                continue
            marker = cleaned.casefold()
            if marker in existing_terms or marker in seen_terms:
                continue
            seen_terms.add(marker)
            normalized_pool.append(cleaned)

        available = normalized_pool[:12]
        if not available:
            if show_hint:
                st.caption(
                    tr(
                        "Aktuell keine Vorschläge verfügbar.",
                        "No suggestions available right now.",
                    )
                )
            return

        st.markdown("<div class='ai-suggestion-box'>", unsafe_allow_html=True)
        st.markdown(
            "<div class='ai-suggestion-box__title'>💡 KI</div>"
            if st.session_state.get("lang", "de") == "de"
            else "<div class='ai-suggestion-box__title'>💡 AI</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='ai-suggestion-box__caption'>{caption}</div>",
            unsafe_allow_html=True,
        )
        widget_prefix = f"ai_suggestions.{target_key}.{widget_suffix}"
        registry_key = f"{widget_prefix}.keys"
        current_keys: list[str] = []
        picked: list[str] = []
        grid_container = st.container()
        for start in range(0, len(available), 4):
            row_values = available[start : start + 4]
            cols = grid_container.columns(len(row_values), gap="small")
            for col, suggestion in zip(cols, row_values):
                cb_key = _boolean_widget_key(widget_prefix, suggestion)
                current_keys.append(cb_key)
                checked = col.checkbox(suggestion, key=cb_key)
                if checked:
                    picked.append(suggestion)
        previous_keys = st.session_state.get(registry_key, [])
        for stale in previous_keys:
            if stale not in current_keys:
                st.session_state.pop(stale, None)
        st.session_state[registry_key] = current_keys
        st.markdown("</div>", unsafe_allow_html=True)
        if picked:
            merged = sorted(
                set(data["requirements"].get(target_key, [])).union(picked),
                key=str.casefold,
            )
            if target_key == "certificates":
                _set_requirement_certificates(data["requirements"], merged)
            else:
                data["requirements"][target_key] = merged
            for suggestion in picked:
                st.session_state.pop(_boolean_widget_key(widget_prefix, suggestion), None)
            st.session_state.pop(registry_key, None)
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.rerun()

        if st.button(
            tr("🔄 Vorschläge aktualisieren", "🔄 Refresh suggestions"),
            key=f"{widget_prefix}.refresh",
            use_container_width=True,
        ):
            for key in st.session_state.get(registry_key, []):
                st.session_state.pop(key, None)
            st.session_state.pop(registry_key, None)
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.rerun()

    responsibilities = data.setdefault("responsibilities", {})
    responsibilities_items = [
        str(item)
        for item in responsibilities.get("items", [])
        if isinstance(item, str)
    ]
    responsibilities_text = "\n".join(responsibilities_items)
    responsibilities_key = "ui.requirements.responsibilities"
    responsibilities_seed_key = f"{responsibilities_key}.__seed"
    if st.session_state.get(responsibilities_seed_key) != responsibilities_text:
        st.session_state[responsibilities_key] = responsibilities_text
        st.session_state[responsibilities_seed_key] = responsibilities_text

    responsibilities_label = tr("Kernaufgaben", "Core responsibilities")
    responsibilities_required = "responsibilities.items" in missing_here
    display_label = (
        f"{responsibilities_label}{REQUIRED_SUFFIX}"
        if responsibilities_required
        else responsibilities_label
    )

    with requirement_panel(
        icon="🧠",
        title=tr("Aufgaben & Verantwortlichkeiten", "Responsibilities & deliverables"),
        caption=tr(
            "Wichtigste Aufgaben als Liste erfassen (eine Zeile je Punkt).",
            "Capture the key responsibilities as a list (one line per item).",
        ),
        tooltip=tr(
            "Nutze Stichpunkte, um klare Verantwortlichkeiten für die Rolle zu dokumentieren.",
            "Use bullet-style lines to document the role's core responsibilities.",
        ),
    ):
        raw_responsibilities = st.text_area(
            display_label,
            key=responsibilities_key,
            value=st.session_state.get(responsibilities_key, responsibilities_text),
            height=200,
            placeholder=tr(
                "z. B. Produkt-Roadmap planen\nStakeholder-Workshops moderieren",
                "e.g., Plan the product roadmap\nFacilitate stakeholder workshops",
            ),
        )
        cleaned_responsibilities = [
            re.sub(r"^[\-\*•]+\s*", "", line.strip())
            for line in raw_responsibilities.splitlines()
            if line.strip()
        ]
        responsibilities["items"] = cleaned_responsibilities
        if responsibilities_required and not cleaned_responsibilities:
            _render_required_caption(True)
        st.session_state[responsibilities_seed_key] = raw_responsibilities

    must_tab, nice_tab, language_tab = st.tabs(
        [
            tr("Muss-Anforderungen", "Must-have"),
            tr("Nice-to-have", "Nice-to-have"),
            tr("Sprachen & Boolean", "Languages & Boolean"),
        ]
    )

    with requirement_panel(
        icon="🔒",
        title=tr("Muss-Anforderungen", "Must-have requirements"),
        caption=tr(
            "Pflichtfelder für die Vorauswahl der Kandidat:innen.",
            "Mandatory inputs used to screen candidates.",
        ),
        tooltip=tr(
            "Alle Angaben in diesem Block sind zwingend für das Matching.",
            "Everything in this block is required for candidate matching.",
        ),
        parent=must_tab,
    ):
        must_cols = st.columns(2, gap="large")
        label_hard_req = tr("Hard Skills (Muss)", "Hard Skills (Must-have)")
        if "requirements.hard_skills_required" in missing_here:
            label_hard_req += REQUIRED_SUFFIX
        with must_cols[0]:
            data["requirements"]["hard_skills_required"] = _chip_multiselect(
                label_hard_req,
                options=data["requirements"].get("hard_skills_required", []),
                values=data["requirements"].get("hard_skills_required", []),
                help_text=tr(
                    "Zwingend benötigte technische Kompetenzen.",
                    "Essential technical competencies.",
                ),
                dropdown=True,
            )
            _render_required_caption(
                "requirements.hard_skills_required" in missing_here
                and not data["requirements"].get("hard_skills_required")
            )
            _render_ai_suggestions(
                source_key="hard_skills",
                target_key="hard_skills_required",
                widget_suffix="must",
                caption=tr(
                    "Empfohlene Skills auf Basis des Jobtitels.",
                    "Recommended skills based on the job title.",
                ),
                show_hint=True,
            )
        label_soft_req = tr("Soft Skills (Muss)", "Soft Skills (Must-have)")
        if "requirements.soft_skills_required" in missing_here:
            label_soft_req += REQUIRED_SUFFIX
        with must_cols[1]:
            data["requirements"]["soft_skills_required"] = _chip_multiselect(
                label_soft_req,
                options=data["requirements"].get("soft_skills_required", []),
                values=data["requirements"].get("soft_skills_required", []),
                help_text=tr(
                    "Unverzichtbare Verhalten- und Teamkompetenzen.",
                    "Critical behavioural and team skills.",
                ),
                dropdown=True,
            )
            _render_required_caption(
                "requirements.soft_skills_required" in missing_here
                and not data["requirements"].get("soft_skills_required")
            )
            _render_ai_suggestions(
                source_key="soft_skills",
                target_key="soft_skills_required",
                widget_suffix="must_soft",
                caption=tr(
                    "KI-Vorschläge für soziale und methodische Kompetenzen.",
                    "AI picks for behavioural and interpersonal strengths.",
                ),
            )

    with requirement_panel(
        icon="✨",
        title=tr("Nice-to-have", "Nice-to-have"),
        caption=tr(
            "Optionale Fähigkeiten für ein ideales Kandidatenprofil.",
            "Optional capabilities that enrich the profile.",
        ),
        tooltip=tr(
            "Diese Angaben sind nicht zwingend, helfen aber bei der Priorisierung.",
            "Not mandatory, but helpful for prioritisation.",
        ),
        parent=nice_tab,
    ):
        nice_cols = st.columns(2, gap="large")
        with nice_cols[0]:
            data["requirements"]["hard_skills_optional"] = _chip_multiselect(
                tr("Hard Skills (Nice-to-have)", "Hard Skills (Nice-to-have)"),
                options=data["requirements"].get("hard_skills_optional", []),
                values=data["requirements"].get("hard_skills_optional", []),
                help_text=tr(
                    "Zusätzliche technische Stärken, die Mehrwert bieten.",
                    "Additional technical strengths that add value.",
                ),
                dropdown=True,
            )
            _render_ai_suggestions(
                source_key="hard_skills",
                target_key="hard_skills_optional",
                widget_suffix="nice",
                caption=tr(
                    "Optionale technische Skills, die die KI empfiehlt.",
                    "Optional technical skills recommended by AI.",
                ),
            )
        with nice_cols[1]:
            data["requirements"]["soft_skills_optional"] = _chip_multiselect(
                tr("Soft Skills (Nice-to-have)", "Soft Skills (Nice-to-have)"),
                options=data["requirements"].get("soft_skills_optional", []),
                values=data["requirements"].get("soft_skills_optional", []),
                help_text=tr(
                    "Wünschenswerte persönliche Eigenschaften.",
                    "Valuable personal attributes.",
                ),
                dropdown=True,
            )
            _render_ai_suggestions(
                source_key="soft_skills",
                target_key="soft_skills_optional",
                widget_suffix="nice_soft",
                caption=tr(
                    "Nice-to-have Soft Skills laut KI-Vorschlag.",
                    "Nice-to-have soft skills suggested by AI.",
                ),
            )

    with requirement_panel(
        icon="🛠️",
        title=tr("Tools, Tech & Zertifikate", "Tools, tech & certificates"),
        caption=tr(
            "Technologien, Systeme und formale Nachweise bündeln.",
            "Capture technologies, systems, and formal certificates.",
        ),
        tooltip=tr(
            "Liste die wichtigsten Werkzeuge sowie verbindliche Zertifikate auf.",
            "List the essential tools together with required certificates.",
        ),
        parent=must_tab,
    ):
        tech_cert_cols = st.columns(2, gap="large")
        with tech_cert_cols[0]:
            data["requirements"]["tools_and_technologies"] = _chip_multiselect(
                tr("Tools & Tech", "Tools & Tech"),
                options=data["requirements"].get("tools_and_technologies", []),
                values=data["requirements"].get("tools_and_technologies", []),
                help_text=tr(
                    "Wichtige Systeme, Plattformen oder Sprachen.",
                    "Key systems, platforms, or languages.",
                ),
                dropdown=True,
            )
            _render_ai_suggestions(
                source_key="tools_and_technologies",
                target_key="tools_and_technologies",
                widget_suffix="tools",
                caption=tr(
                    "Ergänzende Tools & Technologien aus der KI-Analyse.",
                    "Complementary tools & technologies suggested by AI.",
                ),
            )
        with tech_cert_cols[1]:
            certificate_options = _collect_combined_certificates(data["requirements"])
            selected_certificates = _chip_multiselect(
                tr("Zertifikate", "Certificates"),
                options=certificate_options,
                values=certificate_options,
                help_text=tr(
                    "Benötigte Zertifikate oder Nachweise.",
                    "Required certificates or attestations.",
                ),
                dropdown=True,
            )
            _set_requirement_certificates(data["requirements"], selected_certificates)
            _render_ai_suggestions(
                source_key="certificates",
                target_key="certificates",
                widget_suffix="certs",
                caption=tr(
                    "Von der KI empfohlene Zertifikate passend zum Jobtitel.",
                    "AI-recommended certificates that match the job title.",
                ),
            )

    with requirement_panel(
        icon="🌐",
        title=tr("Sprachen & Level", "Languages & level"),
        caption=tr(
            "Kommunikationsanforderungen und gewünschte Sprachkompetenzen.",
            "Communication requirements and desired language skills.",
        ),
        tooltip=tr(
            "Definiere, welche Sprachen verbindlich oder optional sind.",
            "Define which languages are mandatory or optional.",
        ),
        parent=language_tab,
    ):
        lang_cols = st.columns(2, gap="large")
        with lang_cols[0]:
            data["requirements"]["languages_required"] = _chip_multiselect(
                tr("Sprachen", "Languages"),
                options=data["requirements"].get("languages_required", []),
                values=data["requirements"].get("languages_required", []),
                help_text=tr(
                    "Sprachen, die zwingend erforderlich sind.",
                    "Languages that are mandatory for the role.",
                ),
                dropdown=True,
            )
        with lang_cols[1]:
            data["requirements"]["languages_optional"] = _chip_multiselect(
                tr("Optionale Sprachen", "Optional languages"),
                options=data["requirements"].get("languages_optional", []),
                values=data["requirements"].get("languages_optional", []),
                help_text=tr(
                    "Sprachen, die ein Plus darstellen.",
                    "Languages that are a plus.",
                ),
                dropdown=True,
            )

        current_language_level = (
            data["requirements"].get("language_level_english") or ""
        )
        language_level_options = list(CEFR_LANGUAGE_LEVELS)
        if (
            current_language_level
            and current_language_level not in language_level_options
        ):
            language_level_options.append(current_language_level)
        selected_level = st.selectbox(
            tr("Englischniveau", "English level"),
            options=language_level_options,
            index=(
                language_level_options.index(current_language_level)
                if current_language_level in language_level_options
                else 0
            ),
            format_func=_format_language_level_option,
            help=tr(
                "Wähle das minimale Englischniveau für die Rolle.",
                "Select the minimum English proficiency level for the role.",
            ),
        )
        data["requirements"]["language_level_english"] = selected_level

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
    "responsibilities.items",
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
CRITICAL_SECTION_ORDER: tuple[int, ...] = tuple(
    sorted(set(FIELD_SECTION_MAP.values())) or (COMPANY_STEP_INDEX,)
)


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


def _resolve_section_for_field(field: str) -> int:
    """Return the wizard section index responsible for ``field``."""

    section = FIELD_SECTION_MAP.get(field)
    if section is not None:
        return section
    if CRITICAL_SECTION_ORDER:
        return CRITICAL_SECTION_ORDER[0]
    return COMPANY_STEP_INDEX


def _update_section_progress(
    missing_fields: Iterable[str] | None = None,
) -> tuple[int | None, list[int]]:
    """Update session state with completion information for wizard sections."""

    fields = (
        list(missing_fields)
        if missing_fields is not None
        else get_missing_critical_fields()
    )
    fields = list(dict.fromkeys(fields))
    sections_with_missing = {_resolve_section_for_field(field) for field in fields}

    first_incomplete: int | None = None
    for section in CRITICAL_SECTION_ORDER:
        if section in sections_with_missing:
            first_incomplete = section
            break

    if first_incomplete is None and sections_with_missing:
        first_incomplete = _resolve_section_for_field(next(iter(fields)))

    if first_incomplete is None:
        completed_sections = list(CRITICAL_SECTION_ORDER)
    else:
        completed_sections = [
            section
            for section in CRITICAL_SECTION_ORDER
            if section < first_incomplete and section not in sections_with_missing
        ]

    st.session_state[StateKeys.EXTRACTION_MISSING] = fields
    st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] = first_incomplete
    st.session_state[StateKeys.COMPLETED_SECTIONS] = completed_sections
    return first_incomplete, completed_sections


def _step_compensation():
    """Render the compensation and benefits step.

    Returns:
        None
    """

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)
    compensation_header = _format_dynamic_message(
        default=("Leistungen & Benefits", "Rewards & Benefits"),
        context=profile_context,
        variants=[
            (
                (
                    "Vergütung für {job_title} bei {company_name}",
                    "Compensation for {job_title} at {company_name}",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Vergütung für {job_title}",
                    "Compensation for {job_title}",
                ),
                ("job_title",),
            ),
            (
                (
                    "Leistungen bei {company_name}",
                    "Rewards at {company_name}",
                ),
                ("company_name",),
            ),
        ],
    )
    st.subheader(compensation_header)
    compensation_caption = _format_dynamic_message(
        default=(
            "Gehaltsspanne und Zusatzleistungen erfassen.",
            "Capture salary range and benefits.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Gehalt und Benefits für {job_title} bei {company_name} festhalten.",
                    "Capture salary and benefits for {job_title} at {company_name}.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Gehalt und Benefits für {job_title} festhalten.",
                    "Capture salary and benefits for {job_title}.",
                ),
                ("job_title",),
            ),
        ],
    )
    st.caption(compensation_caption)
    data = profile

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
        tr("Mitarbeiterbeteiligung?", "Equity?"),
        value=bool(data["compensation"].get("equity_offered")),
    )
    lang = st.session_state.get("lang", "de")
    industry_context = data.get("company", {}).get("industry", "")
    fallback_benefits = get_static_benefit_shortlist(
        lang=lang, industry=industry_context
    )
    sugg_benefits = st.session_state.get(StateKeys.BENEFIT_SUGGESTIONS, [])
    benefit_options = sorted(
        set(
            fallback_benefits
            + data["compensation"].get("benefits", [])
            + sugg_benefits
        )
    )
    data["compensation"]["benefits"] = _chip_multiselect(
        tr("Leistungen", "Benefits"),
        options=benefit_options,
        values=data["compensation"].get("benefits", []),
    )

    if st.button("💡 " + tr("Benefits vorschlagen", "Suggest Benefits")):
        job_title = data.get("position", {}).get("job_title", "")
        industry = data.get("company", {}).get("industry", "")
        existing = "\n".join(data["compensation"].get("benefits", []))
        new_sugg, err, used_fallback = get_benefit_suggestions(
            job_title,
            industry,
            existing,
            lang=lang,
        )
        if used_fallback:
            st.info(
                tr(
                    "Keine KI-Vorschläge verfügbar – zeige Standardliste.",
                    "No AI suggestions available – showing fallback list.",
                )
            )
        elif err:
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

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)
    process_header = _format_dynamic_message(
        default=("Prozess", "Process"),
        context=profile_context,
        variants=[
            (
                (
                    "Bewerbungsprozess bei {company_name}",
                    "Hiring process at {company_name}",
                ),
                ("company_name",),
            ),
            (
                (
                    "Prozess für {job_title}",
                    "Process for {job_title}",
                ),
                ("job_title",),
            ),
        ],
    )
    st.subheader(process_header)
    process_caption = _format_dynamic_message(
        default=(
            "Ablauf des Bewerbungsprozesses skizzieren.",
            "Outline the hiring process steps.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Ablauf für den {job_title}-Prozess bei {company_name} skizzieren.",
                    "Outline the {job_title} process at {company_name}.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Ablauf für den {job_title}-Prozess skizzieren.",
                    "Outline the {job_title} process steps.",
                ),
                ("job_title",),
            ),
        ],
    )
    st.caption(process_caption)
    data = profile["process"]

    _render_stakeholders(data, "ui.process.stakeholders")
    _render_phases(data, data.get("stakeholders", []), "ui.process.phases")

    c1, c2 = st.columns(2)
    original_timeline = data.get("recruitment_timeline", "")
    default_start, default_end = _timeline_default_range(original_timeline)
    timeline_selection = c1.date_input(
        tr("Gesamt-Timeline", "Overall timeline"),
        value=(default_start, default_end),
        key="ui.process.recruitment_timeline",
    )
    start_date, end_date = _normalize_date_selection(timeline_selection)
    changed = (start_date, end_date) != (default_start, default_end)
    if (
        original_timeline
        and not _parse_timeline_range(str(original_timeline))[0]
        and not changed
    ):
        data["recruitment_timeline"] = str(original_timeline)
    else:
        data["recruitment_timeline"] = _format_timeline_string(start_date, end_date)
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
        _render_onboarding_section(data, "ui.process.onboarding")

    # Inline follow-up questions for Process section
    _render_followups_for_section(("process.",), profile)


def _summary_company() -> None:
    """Editable summary tab for company information."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    summary_company_label = tr("Firma", "Company") + REQUIRED_SUFFIX
    summary_company_lock = _field_lock_config(
        "company.name",
        summary_company_label,
        container=c1,
        context="summary",
    )
    name = c1.text_input(
        summary_company_lock["label"],
        value=data["company"].get("name", ""),
        **_apply_field_lock_kwargs(
            summary_company_lock,
            {
                "key": "ui.summary.company.name",
                "help": tr("Dieses Feld ist erforderlich", "This field is required"),
            },
        ),
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
    summary_title_label = tr("Jobtitel", "Job title") + REQUIRED_SUFFIX
    summary_title_lock = _field_lock_config(
        "position.job_title",
        summary_title_label,
        container=c1,
        context="summary",
    )
    job_title = c1.text_input(
        summary_title_lock["label"],
        value=data["position"].get("job_title", ""),
        **_apply_field_lock_kwargs(
            summary_title_lock,
            {
                "key": "ui.summary.position.job_title",
                "help": tr("Dieses Feld ist erforderlich", "This field is required"),
            },
        ),
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
    summary_city_lock = _field_lock_config(
        "location.primary_city",
        tr("Stadt", "City"),
        container=c1,
        context="summary",
    )
    loc_city = c1.text_input(
        summary_city_lock["label"],
        value=data.get("location", {}).get("primary_city", ""),
        **_apply_field_lock_kwargs(
            summary_city_lock,
            {"key": "ui.summary.location.primary_city"},
        ),
    )
    summary_country_lock = _field_lock_config(
        "location.country",
        tr("Land", "Country"),
        container=c2,
        context="summary",
    )
    loc_country = c2.text_input(
        summary_country_lock["label"],
        value=data.get("location", {}).get("country", ""),
        **_apply_field_lock_kwargs(
            summary_country_lock,
            {"key": "ui.summary.location.country"},
        ),
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
    combined_certs = _collect_combined_certificates(data["requirements"])
    certs = st.text_area(
        tr("Zertifikate", "Certificates"),
        value=", ".join(combined_certs),
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
    new_certs = [s.strip() for s in certs.split(",") if s.strip()]
    _update_profile("requirements.certificates", new_certs)
    _update_profile("requirements.certifications", new_certs)


def _summary_employment() -> None:
    """Editable summary tab for employment details."""

    data = st.session_state[StateKeys.PROFILE]
    c1, c2 = st.columns(2)
    job_options = [
        "full_time",
        "part_time",
        "contract",
        "internship",
        "working_student",
        "trainee_program",
        "apprenticeship",
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
        tr("Mitarbeiterbeteiligung?", "Equity?"),
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
        tr("Leistungen", "Benefits"),
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
    original_timeline = process.get("recruitment_timeline", "")
    default_start, default_end = _timeline_default_range(original_timeline)
    summary_selection = c1.date_input(
        tr("Gesamt-Timeline", "Overall timeline"),
        value=(default_start, default_end),
        key="ui.summary.process.recruitment_timeline",
    )
    start_date, end_date = _normalize_date_selection(summary_selection)
    changed = (start_date, end_date) != (default_start, default_end)
    if (
        original_timeline
        and not _parse_timeline_range(str(original_timeline))[0]
        and not changed
    ):
        timeline = str(original_timeline)
    else:
        timeline = _format_timeline_string(start_date, end_date)
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
        _render_onboarding_section(
            process, "ui.summary.process.onboarding", allow_generate=False
        )
        onboarding = process.get("onboarding_process", "")

    _update_profile("process.recruitment_timeline", timeline)
    _update_profile("process.process_notes", notes)
    _update_profile("process.application_instructions", instructions)
    _update_profile("process.onboarding_process", onboarding)


def _summary_group_counts(data: Mapping[str, Any], lang: str) -> dict[str, int]:
    """Return the number of collected entries per summary tab group."""

    counts: dict[str, int] = {}
    for field in JOB_AD_FIELDS:
        entries = _job_ad_field_entries(data, field, lang)
        if not entries:
            continue
        counts[field.group] = counts.get(field.group, 0) + len(entries)
    return counts


def _render_summary_group_entries(
    group: str,
    data: Mapping[str, Any],
    lang: str,
) -> None:
    """Display collected values for the summary view."""

    is_de = lang.lower().startswith("de")

    group_fields = [field for field in JOB_AD_FIELDS if field.group == group]
    field_entries: dict[str, list[tuple[str, str]]] = {}
    for field in group_fields:
        entries = _job_ad_field_entries(data, field, lang)
        if entries:
            field_entries[field.key] = entries

    ordered_fields = [field for field in group_fields if field.key in field_entries]

    if not ordered_fields:
        st.info(
            tr(
                "Für diesen Abschnitt liegen keine Angaben vor.",
                "No entries available for this section.",
            )
        )
        return

    for index, field_def in enumerate(ordered_fields):
        entries = field_entries[field_def.key]

        label = field_def.label_de if is_de else field_def.label_en
        description = field_def.description_de if is_de else field_def.description_en

        field_box = st.container()
        field_box.markdown("<div class='summary-field-card'>", unsafe_allow_html=True)
        source_icon = _summary_source_icon_html(field_def.key)
        icon_html = f" {source_icon}" if source_icon else ""
        field_box.markdown(
            f"<div class='summary-field-title'>{html.escape(label)}{icon_html}</div>",
            unsafe_allow_html=True,
        )
        if description:
            field_box.markdown(
                f"<div class='summary-field-description'>{html.escape(description)}</div>",
                unsafe_allow_html=True,
            )

        items_html = "".join(
            f"<li>{html.escape(entry_text)}</li>" for _, entry_text in entries
        )
        field_box.markdown(
            f"<ul class='summary-field-list'>{items_html}</ul>",
            unsafe_allow_html=True,
        )

        field_box.markdown("</div>", unsafe_allow_html=True)

        if index < len(ordered_fields) - 1:
            st.markdown("<div class='summary-field-gap'></div>", unsafe_allow_html=True)


def _textarea_height(content: str) -> int:
    """Return a dynamic textarea height for generated documents."""

    if not content:
        return 240
    line_count = content.count("\n") + 1
    return min(900, max(240, line_count * 28))


def _render_summary_highlights(profile: NeedAnalysisProfile) -> None:
    """Render a short highlight block with the most relevant profile facts."""

    placeholder = tr("Noch offen", "TBD")

    job_title = (profile.position.job_title or "").strip() or placeholder
    company_name = (
        (profile.company.name or profile.company.brand_name or "").strip()
        or placeholder
    )

    location_parts: list[str] = []
    primary_city = (profile.location.primary_city or "").strip()
    country = (profile.location.country or "").strip()
    if primary_city:
        location_parts.append(primary_city)
    if country:
        location_parts.append(country)
    location_value = ", ".join(location_parts) if location_parts else placeholder

    compensation = profile.compensation
    salary_values: list[str] = []
    if compensation.salary_min is not None:
        salary_values.append(f"{compensation.salary_min:,.0f}")
    if compensation.salary_max is not None:
        salary_values.append(f"{compensation.salary_max:,.0f}")

    salary_range = ""
    if salary_values:
        if len(salary_values) == 2:
            salary_range = tr("{min} – {max}", "{min} – {max}").format(
                min=salary_values[0], max=salary_values[1]
            )
        else:
            salary_range = salary_values[0]

    currency = (compensation.currency or "").strip()
    period = (compensation.period or "").strip()

    if salary_range:
        if currency:
            salary_range = f"{currency} {salary_range}"
        if period:
            salary_range = tr("{base} pro {period}", "{base} per {period}").format(
                base=salary_range, period=period
            )
    elif compensation.salary_provided:
        salary_range = tr("Gehalt vorhanden", "Salary provided")
    else:
        salary_range = placeholder

    requirements = profile.requirements

    def _first_items(values: Sequence[str]) -> list[str]:
        return [item.strip() for item in values if item and item.strip()][:5]

    hard_skills = _first_items(requirements.hard_skills_required)
    if not hard_skills:
        hard_skills = _first_items(requirements.hard_skills_optional)
    soft_skills = _first_items(requirements.soft_skills_required)
    if not soft_skills:
        soft_skills = _first_items(requirements.soft_skills_optional)

    hard_value = ", ".join(hard_skills) if hard_skills else placeholder
    soft_value = ", ".join(soft_skills) if soft_skills else placeholder

    highlight_title = tr("Wesentliche Eckdaten", "Key highlights")
    job_title_label = tr("Jobtitel", "Job title")
    company_label = tr("Unternehmen", "Company")
    location_label = tr("Standort", "Location")
    salary_label = tr("Vergütung", "Compensation")
    hard_label = tr("Fachliche Skills", "Hard skills")
    soft_label = tr("Soziale Skills", "Soft skills")

    bullets = [
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=job_title_label, value=job_title
        ),
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=company_label, value=company_name
        ),
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=location_label, value=location_value
        ),
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=salary_label, value=salary_range
        ),
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=hard_label, value=hard_value
        ),
        tr("- **{label}:** {value}", "- **{label}:** {value}").format(
            label=soft_label, value=soft_value
        ),
    ]

    with st.container():
        st.markdown(f"#### {highlight_title}")
        st.markdown("\n".join(bullets))


def _step_summary(schema: dict, _critical: list[str]):
    """Render the summary step and offer follow-up questions.

    Args:
        schema: Schema defining allowed fields.
        critical: Keys that must be present in ``data``.

    Returns:
        None
    """

    data = st.session_state[StateKeys.PROFILE]
    lang = st.session_state.get("lang", "de")

    try:
        profile = NeedAnalysisProfile.model_validate(data)
    except Exception:
        profile = NeedAnalysisProfile()

    profile_payload = profile.model_dump(mode="json")
    profile_payload["lang"] = lang

    profile_bytes, profile_mime, profile_ext = prepare_clean_json(profile_payload)
    job_title_value = (profile.position.job_title or "").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", job_title_value).strip("-")
    if not safe_stem:
        safe_stem = "need-analysis-profile"
    profile_filename = f"{safe_stem}.{profile_ext}"

    header_cols = st.columns((1, 0.45), gap="small")
    with header_cols[0]:
        st.subheader(tr("Zusammenfassung", "Summary"))
    with header_cols[1]:
        st.download_button(
            tr("⬇️ JSON-Profil exportieren", "⬇️ Export JSON profile"),
            profile_bytes,
            file_name=profile_filename,
            mime=profile_mime,
            use_container_width=True,
            key="download_profile_json",
        )

    st.caption(
        tr(
            "Überprüfen Sie Ihre Angaben und laden Sie das saubere JSON-Profil über den Button herunter.",
            "Review your entries and use the button to download the clean JSON profile.",
        )
    )

    _render_confidence_legend()

    _render_summary_highlights(profile)

    tab_labels = [
        tr("Unternehmen", "Company"),
        tr("Basisdaten", "Basic info"),
        tr("Anforderungen", "Requirements"),
        tr("Beschäftigung", "Employment"),
        tr("Leistungen & Benefits", "Rewards & Benefits"),
        tr("Prozess", "Process"),
    ]
    group_keys = [
        "company",
        "basic",
        "requirements",
        "employment",
        "compensation",
        "process",
    ]

    mode_options = {
        "overview": tr("Überblick", "Overview"),
        "edit": tr("Bearbeiten", "Edit"),
    }
    mode_label = tr("Ansicht", "View mode")
    if (
        StateKeys.SUMMARY_SELECTED_GROUP not in st.session_state
        or st.session_state[StateKeys.SUMMARY_SELECTED_GROUP] not in mode_options
    ):
        st.session_state[StateKeys.SUMMARY_SELECTED_GROUP] = "overview"
    summary_mode = st.radio(
        mode_label,
        options=list(mode_options.keys()),
        format_func=lambda opt: mode_options[opt],
        key=StateKeys.SUMMARY_SELECTED_GROUP,
        horizontal=True,
    )

    tab_definitions = list(zip(group_keys, tab_labels))
    summary_helpers: dict[str, Callable[[], None]] = {
        "company": _summary_company,
        "basic": _summary_position,
        "requirements": _summary_requirements,
        "employment": _summary_employment,
        "compensation": _summary_compensation,
        "process": _summary_process,
    }

    if summary_mode == "overview":
        overview_counts = _summary_group_counts(data, lang)
        overview_title = tr(
            "Überblick über erfasste Angaben",
            "Overview of captured entries",
        )
        st.markdown(f"### {overview_title}")
        entry_label = tr("Einträge", "Entries")
        empty_label = tr("Noch keine Angaben", "No entries yet")
    else:
        edit_title = tr("Angaben bearbeiten", "Edit captured details")
        st.markdown(f"### {edit_title}")
        st.caption(
            tr(
                "Passe die Inhalte der einzelnen Bereiche direkt in den Tabs an.",
                "Adjust the contents of each section directly within the tabs.",
            )
        )

    summary_tabs = st.tabs([label for _, label in tab_definitions])
    for tab, (group, _label) in zip(summary_tabs, tab_definitions):
        with tab:
            if summary_mode == "overview":
                count = overview_counts.get(group, 0)
                subtitle = f"{count} {entry_label}" if count else empty_label
                st.caption(subtitle)
                _render_summary_group_entries(group, data, lang)
            else:
                helper = summary_helpers.get(group)
                if helper:
                    helper()
                else:
                    st.info(
                        tr(
                            "Für diesen Bereich ist keine Bearbeitung verfügbar.",
                            "Editing is not available for this section.",
                        )
                    )

    st.caption(
        tr(
            "Alle verfügbaren Angaben werden automatisch in die finale Darstellung übernommen.",
            "All available information is automatically included in the final output.",
        )
    )
    st.divider()

    default_boolean_query = build_boolean_search(profile)
    profile_signature = _boolean_profile_signature(profile)
    stored_signature = st.session_state.get(BOOLEAN_PROFILE_SIGNATURE)
    if stored_signature != profile_signature:
        for widget_key in list(st.session_state.get(BOOLEAN_WIDGET_KEYS, [])):
            st.session_state.pop(widget_key, None)
        st.session_state[BOOLEAN_WIDGET_KEYS] = []
        st.session_state[BOOLEAN_PROFILE_SIGNATURE] = profile_signature
        st.session_state[StateKeys.BOOLEAN_STR] = default_boolean_query
    elif StateKeys.BOOLEAN_STR not in st.session_state:
        st.session_state[StateKeys.BOOLEAN_STR] = default_boolean_query

    boolean_skill_terms = _boolean_skill_terms(profile)
    boolean_title_synonyms = _boolean_title_synonyms(profile)

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

    base_url = st.session_state.get(StateKeys.COMPANY_PAGE_BASE) or ""
    style_reference = _job_ad_style_reference(profile_payload, base_url or None)

    suggestions = suggest_target_audiences(profile, lang)
    available_field_keys = _job_ad_available_field_keys(profile_payload, lang)

    target_value = st.session_state.get(StateKeys.JOB_AD_SELECTED_AUDIENCE, "")

    st.markdown(tr("#### Weiterverarbeitung", "#### Next steps"))
    next_step_cols = st.columns((1.4, 1.1, 1.2), gap="large")

    with next_step_cols[0]:
        st.markdown(f"##### {tr('Zielgruppe & Ton', 'Audience & tone')}")
        brand_initial = data.get("company", {}).get("brand_keywords")
        brand_value_input = st.text_input(
            tr("Brand-Ton oder Keywords", "Brand tone or keywords"),
            value=brand_initial or "",
            key="ui.summary.company.brand_keywords",
        )
        brand_value = brand_value_input if brand_value_input.strip() else None
        _update_profile("company.brand_keywords", brand_value)

        if suggestions:
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

        st.caption(
            tr(
                "Alle Inhalte und die gewählte Zielgruppe fließen in die Anzeige ein.",
                "All available content and the chosen target audience feed into the job ad.",
            )
        )

    with next_step_cols[1]:
        st.markdown(f"##### {tr('Exportoptionen', 'Export options')}")
        if UIKeys.JOB_AD_FORMAT not in st.session_state:
            st.session_state[UIKeys.JOB_AD_FORMAT] = "docx"
        format_options = {
            "docx": "DOCX",
            "pdf": "PDF",
            "markdown": "Markdown",
            "json": "JSON",
        }
        format_choice = st.selectbox(
            tr("Export-Format", "Export format"),
            options=list(format_options.keys()),
            format_func=lambda k: format_options[k],
            key=UIKeys.JOB_AD_FORMAT,
        )

        font_default = st.session_state.get(
            StateKeys.JOB_AD_FONT_CHOICE, FONT_CHOICES[0]
        )
        if StateKeys.JOB_AD_FONT_CHOICE not in st.session_state:
            st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = font_default
        if UIKeys.JOB_AD_FONT not in st.session_state:
            st.session_state[UIKeys.JOB_AD_FONT] = font_default
        font_index = (
            FONT_CHOICES.index(st.session_state.get(UIKeys.JOB_AD_FONT, font_default))
            if st.session_state.get(UIKeys.JOB_AD_FONT, font_default) in FONT_CHOICES
            else 0
        )
        st.selectbox(
            tr("Schriftart für Export", "Export font"),
            FONT_CHOICES,
            index=font_index,
            key=UIKeys.JOB_AD_FONT,
            on_change=_update_job_ad_font,
        )
        st.caption(
            tr(
                "Die Auswahl gilt für Stellenanzeige und Interviewleitfaden, sofern unterstützt.",
                "Selection applies to job ad and interview guide when supported.",
            )
        )

    with next_step_cols[2]:
        st.markdown(f"##### {tr('Branding-Assets', 'Brand assets')}")
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
                    logo_bytes, caption=tr("Aktuelles Logo", "Current logo"), width=180
                )
            except Exception:
                st.caption(
                    tr("Logo erfolgreich geladen.", "Logo uploaded successfully.")
                )
            if st.button(tr("Logo entfernen", "Remove logo"), key="job_ad_logo_remove"):
                st.session_state[StateKeys.JOB_AD_LOGO_DATA] = None
                st.rerun()

    st.divider()

    st.session_state[StateKeys.JOB_AD_SELECTED_AUDIENCE] = target_value

    filtered_profile = _prepare_job_ad_data(profile_payload)
    filtered_profile["lang"] = lang

    raw_selection = st.session_state.get(StateKeys.JOB_AD_SELECTED_FIELDS)
    widget_state_exists = any(
        f"{UIKeys.JOB_AD_FIELD_PREFIX}{group}" in st.session_state
        for group in group_keys
    )
    if raw_selection is None:
        current_selection: set[str] = set()
    else:
        current_selection = set(raw_selection)
    if not widget_state_exists and not current_selection:
        stored_selection = set(available_field_keys)
    else:
        stored_selection = {key for key in current_selection if key in available_field_keys}

    is_de = lang.lower().startswith("de")
    field_labels = {
        field.key: field.label_de if is_de else field.label_en
        for field in JOB_AD_FIELDS
    }

    st.markdown(tr("##### Feldauswahl", "##### Field selection"))
    st.caption(
        tr(
            "Wähle die Inhalte, die in die Stellenanzeige übernommen werden.",
            "Choose which sections should be included in the job ad.",
        )
    )

    aggregated_selection: set[str] = set()
    for group in group_keys:
        group_fields = [
            field
            for field in JOB_AD_FIELDS
            if field.group == group and field.key in available_field_keys
        ]
        if not group_fields:
            continue

        group_label_de, group_label_en = JOB_AD_GROUP_LABELS.get(group, (group, group))
        widget_label = group_label_de if is_de else group_label_en
        widget_key = f"{UIKeys.JOB_AD_FIELD_PREFIX}{group}"
        options = [field.key for field in group_fields]
        default_values = [key for key in options if key in stored_selection]

        existing_values = st.session_state.get(widget_key)
        if existing_values is not None:
            sanitized_values = [value for value in existing_values if value in options]
            if sanitized_values != existing_values:
                st.session_state[widget_key] = sanitized_values

        selected_group_values = st.multiselect(
            widget_label,
            options,
            default=default_values,
            format_func=lambda key, labels=field_labels: labels.get(key, key),
            key=widget_key,
        )
        aggregated_selection.update(selected_group_values)

    selected_fields = resolve_job_ad_field_selection(
        available_field_keys, aggregated_selection
    )
    st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = set(selected_fields)

    st.markdown(tr("### 1. Stellenanzeige-Generator", "### 1. Job ad generator"))
    st.caption(
        tr(
            "Verwalte Inhalte, Tonalität und Optimierungen für deine Anzeige.",
            "Manage content, tone, and optimisations for your job ad.",
        )
    )

    manual_entries: list[dict[str, str]] = list(
        st.session_state.get(StateKeys.JOB_AD_MANUAL_ENTRIES, [])
    )
    with st.expander(tr("Manuelle Ergänzungen", "Manual additions")):
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
                entry = {
                    "title": manual_title.strip(),
                    "content": manual_text.strip(),
                }
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

    has_content = bool(selected_fields)
    disabled = not has_content or not target_value
    if st.button(
        tr("📝 Stellenanzeige generieren", "📝 Generate job ad"),
        disabled=disabled,
        type="primary",
    ):
        _generate_job_ad_content(
            filtered_profile,
            selected_fields,
            target_value,
            list(manual_entries),
            style_reference,
            lang,
        )

    job_ad_text = st.session_state.get(StateKeys.JOB_AD_MD)
    output_key = UIKeys.JOB_AD_OUTPUT
    existing_output = st.session_state.get(output_key, "")
    display_text = job_ad_text if job_ad_text is not None else existing_output
    if (
        output_key not in st.session_state
        or st.session_state[output_key] != display_text
    ):
        st.session_state[output_key] = display_text

    current_text = st.session_state.get(output_key, "")
    st.text_area(
        tr("Generierte Stellenanzeige", "Generated job ad"),
        height=_textarea_height(current_text),
        key=output_key,
    )

    if not job_ad_text and current_text:
        st.info(
            tr(
                "Profil geändert – bitte Anzeige neu generieren.",
                "Profile updated – please regenerate the job ad.",
            )
        )

    if job_ad_text:
        seo_data = seo_optimize(job_ad_text)
        keywords: list[str] = list(seo_data.get("keywords", []))
        meta_description: str = str(seo_data.get("meta_description", ""))
        if keywords or meta_description:
            with st.expander(tr("SEO-Empfehlungen", "SEO insights")):
                if keywords:
                    st.write(
                        tr("Top-Schlüsselbegriffe", "Top keywords")
                        + ": "
                        + ", ".join(keywords)
                    )
                if meta_description:
                    st.write(
                        tr("Meta-Beschreibung", "Meta description")
                        + ": "
                        + meta_description
                    )

        findings = st.session_state.get(StateKeys.BIAS_FINDINGS) or []
        if findings:
            with st.expander(tr("Bias-Check", "Bias check")):
                for finding in findings:
                    st.warning(finding)

        format_choice = st.session_state.get(UIKeys.JOB_AD_FORMAT, "markdown")
        font_choice = st.session_state.get(StateKeys.JOB_AD_FONT_CHOICE)
        logo_bytes = st.session_state.get(StateKeys.JOB_AD_LOGO_DATA)
        company_name = (
            profile.company.brand_name
            or profile.company.name
            or str(_job_ad_get_value(profile_payload, "company.name") or "").strip()
            or None
        )
        job_title = (
            profile.position.job_title
            or str(
                _job_ad_get_value(profile_payload, "position.job_title") or ""
            ).strip()
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
            tr("⬇️ Anzeige herunterladen", "⬇️ Download job ad"),
            payload,
            file_name=f"{safe_stem}.{ext}",
            mime=mime,
            key="download_job_ad",
        )

        st.markdown(tr("##### Anpassungswünsche", "##### Refinement requests"))
        feedback = st.text_area(
            tr("Was soll angepasst werden?", "What should be adjusted?"),
            key=UIKeys.JOB_AD_FEEDBACK,
        )
        if st.button(
            tr("🔄 Anzeige anpassen", "🔄 Refine job ad"),
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
                    tr("Verfeinerung fehlgeschlagen", "Refinement failed") + f": {e}"
                )

    st.markdown(tr("### 2. Interview-Prep-Sheet", "### 2. Interview prep sheet"))
    st.caption(
        tr(
            "Erstelle Leitfäden und passe sie an verschiedene Zielgruppen an.",
            "Generate guides and tailor them for different audiences.",
        )
    )

    tone_col, question_col = st.columns((1, 1))
    with tone_col:
        selected_tone = st.selectbox(
            tr("Interviewleitfaden-Ton", "Interview guide tone"),
            options=list(tone_options.keys()),
            format_func=lambda k: tone_labels.get(k, k),
            key=UIKeys.TONE_SELECT,
        )
        st.session_state["tone"] = tone_options.get(selected_tone)

    with question_col:
        if UIKeys.NUM_QUESTIONS not in st.session_state:
            st.session_state[UIKeys.NUM_QUESTIONS] = 5
        st.slider(
            tr("Anzahl Interviewfragen", "Number of interview questions"),
            min_value=3,
            max_value=10,
            key=UIKeys.NUM_QUESTIONS,
        )

    audience_labels = {
        "general": tr("Allgemeines Interviewteam", "General interview panel"),
        "technical": tr("Technisches Fachpublikum", "Technical panel"),
        "leadership": tr("Führungsteam", "Leadership panel"),
    }
    if UIKeys.AUDIENCE_SELECT not in st.session_state:
        st.session_state[UIKeys.AUDIENCE_SELECT] = st.session_state.get(
            StateKeys.INTERVIEW_AUDIENCE, "general"
        )
    audience = st.selectbox(
        tr("Interview-Zielgruppe", "Interview audience"),
        options=list(audience_labels.keys()),
        format_func=lambda key: audience_labels.get(key, key),
        key=UIKeys.AUDIENCE_SELECT,
        help=tr(
            "Steuert Fokus und Tonfall des generierten Leitfadens.",
            "Controls the focus and tone of the generated guide.",
        ),
    )
    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience

    selected_num = st.session_state.get(UIKeys.NUM_QUESTIONS, 5)
    if st.button(tr("🗂️ Interviewleitfaden generieren", "🗂️ Generate guide")):
        _generate_interview_guide_content(
            profile_payload,
            lang,
            selected_num,
            audience=audience,
        )

    guide_text = st.session_state.get(StateKeys.INTERVIEW_GUIDE_MD, "")
    if guide_text:
        output_key = UIKeys.INTERVIEW_OUTPUT
        if (
            output_key not in st.session_state
            or st.session_state.get(output_key) != guide_text
        ):
            st.session_state[output_key] = guide_text
        st.text_area(
            tr("Generierter Leitfaden", "Generated guide"),
            height=_textarea_height(guide_text),
            key=output_key,
        )
        guide_format = st.session_state.get(UIKeys.JOB_AD_FORMAT, "docx")
        font_choice = st.session_state.get(StateKeys.JOB_AD_FONT_CHOICE)
        logo_bytes = st.session_state.get(StateKeys.JOB_AD_LOGO_DATA)
        guide_title = profile.position.job_title or "interview-guide"
        safe_stem = (
            re.sub(r"[^A-Za-z0-9_-]+", "-", guide_title).strip("-")
            or "interview-guide"
        )
        export_font = font_choice if guide_format in {"docx", "pdf"} else None
        export_logo = logo_bytes if guide_format in {"docx", "pdf"} else None
        payload, mime, ext = prepare_download_data(
            guide_text,
            guide_format,
            key="interview",
            title=guide_title,
            font=export_font,
            logo=export_logo,
            company_name=profile.company.name,
        )
        st.download_button(
            tr("⬇️ Leitfaden herunterladen", "⬇️ Download guide"),
            payload,
            file_name=f"{safe_stem}.{ext}",
            mime=mime,
            key="download_interview",
        )

    st.markdown(tr("### 3. Boolean Searchstring", "### 3. Boolean search string"))
    st.caption(
        tr(
            "Nutze Jobtitel und Skills, um zielgenaue Suchen aufzubauen.",
            "Use job titles and skills to craft precise search strings.",
        )
    )
    _render_boolean_interactive_section(
        profile,
        boolean_skill_terms=boolean_skill_terms,
        boolean_title_synonyms=boolean_title_synonyms,
    )

    st.markdown(
        tr("### 4. Interne Prozesse definieren", "### 4. Define internal processes")
    )
    st.caption(
        tr(
            "Ordne Informationsschleifen zu und halte Aufgaben für jede Phase fest.",
            "Assign information loops and capture tasks for each process phase.",
        )
    )

    process_data = data.get("process", {}) or {}
    stakeholders = process_data.get("stakeholders", []) or []
    phases = process_data.get("phases", []) or []

    process_cols = st.columns(2, gap="large")
    with process_cols[0]:
        st.markdown(tr("#### Informationsschleifen", "#### Information loops"))
        phase_labels = _phase_display_labels(phases)
        phase_indices = list(range(len(phase_labels)))
        if not stakeholders:
            st.info(
                tr(
                    "Keine Stakeholder hinterlegt – Schritt 'Prozess' ausfüllen, um Personen zu ergänzen.",
                    "No stakeholders available – populate the Process step to add contacts.",
                )
            )
        else:
            for idx, person in enumerate(stakeholders):
                display_name = person.get("name") or tr(
                    "Stakeholder {number}", "Stakeholder {number}"
                ).format(number=idx + 1)
                st.markdown(f"**{display_name}**")
                existing_selection = _filter_phase_indices(
                    person.get("information_loop_phases", []), len(phase_indices)
                )
                if existing_selection != person.get("information_loop_phases"):
                    person["information_loop_phases"] = existing_selection
                person["information_loop_phases"] = st.multiselect(
                    tr("Phasen", "Phases"),
                    options=phase_indices,
                    default=existing_selection,
                    format_func=_phase_label_formatter(phase_labels),
                    key=f"summary.process.loop.{idx}",
                    disabled=not phase_indices,
                )
            if not phase_indices:
                st.info(
                    tr(
                        "Lege Prozessphasen an, um Informationsschleifen zuzuweisen.",
                        "Create process phases to assign information loops.",
                    )
                )

    with process_cols[1]:
        st.markdown(tr("#### Aufgaben & Übergaben", "#### Tasks & handovers"))
        if not phases:
            st.info(
                tr(
                    "Noch keine Phasen definiert – Schritt 'Prozess' ergänzt Aufgaben.",
                    "No phases defined yet – use the Process step to add them.",
                )
            )
        else:
            for idx, phase in enumerate(phases):
                phase_name = phase.get("name") or tr(
                    "Phase {number}", "Phase {number}"
                ).format(number=idx + 1)
                st.markdown(f"**{phase_name}**")
                current_tasks = phase.get("task_assignments", "")
                phase["task_assignments"] = st.text_area(
                    tr("Aufgabenbeschreibung", "Task notes"),
                    value=current_tasks,
                    key=f"summary.process.tasks.{idx}",
                    label_visibility="collapsed",
                    placeholder=tr(
                        "To-dos, Verantwortlichkeiten und Hand-offs …",
                        "To-dos, responsibilities, and hand-offs …",
                    ),
                )

    manual_entries = list(st.session_state.get(StateKeys.JOB_AD_MANUAL_ENTRIES, []))

    followup_items = st.session_state.get(StateKeys.FOLLOWUPS) or []
    if followup_items:
        st.divider()
        st.markdown(tr("**Vorgeschlagene Fragen:**", "**Suggested questions:**"))

        entry_specs: list[tuple[str, str, str]] = []
        for item in followup_items:
            field_path = item.get("field") or item.get("key") or ""
            question_text = item.get("question") or ""
            if not field_path or not question_text:
                continue
            input_key = f"fu_{field_path}"
            existing_value = str(get_in(data, field_path, "") or "")
            if input_key not in st.session_state:
                st.session_state[input_key] = existing_value
            entry_specs.append((field_path, question_text, input_key))

        if entry_specs:
            stored_snapshot = dict(
                st.session_state.get(StateKeys.SUMMARY_FOLLOWUP_SNAPSHOT, {})
            )
            with st.form("summary_followups_form"):
                for field_path, question_text, input_key in entry_specs:
                    st.markdown(f"**{question_text}**")
                    st.text_input(
                        question_text,
                        key=input_key,
                        value=st.session_state.get(input_key, ""),
                        label_visibility="collapsed",
                    )
                submit_label = tr(
                    "Folgeantworten anwenden",
                    "Apply follow-up answers",
                )
                submitted = st.form_submit_button(submit_label, type="primary")

            if submitted:
                answers = {
                    field_path: st.session_state.get(input_key, "")
                    for field_path, _question, input_key in entry_specs
                }
                trimmed_answers = {
                    field: value.strip() for field, value in answers.items()
                }
                for field_path, _question, input_key in entry_specs:
                    st.session_state[input_key] = trimmed_answers.get(
                        field_path, ""
                    )
                changed = trimmed_answers != stored_snapshot
                st.session_state[StateKeys.SUMMARY_FOLLOWUP_SNAPSHOT] = (
                    trimmed_answers
                )

                if changed:
                    job_generated, interview_generated = _apply_followup_updates(
                        trimmed_answers,
                        data=data,
                        filtered_profile=filtered_profile,
                        profile_payload=profile_payload,
                        target_value=target_value,
                        manual_entries=manual_entries,
                        style_reference=style_reference,
                        lang=lang,
                        selected_fields=selected_fields,
                        num_questions=st.session_state.get(
                            UIKeys.NUM_QUESTIONS, 5
                        ),
                        warn_on_length=False,
                        show_feedback=True,
                    )
                    if job_generated or interview_generated:
                        st.toast(
                            tr(
                                "Folgeantworten übernommen – Inhalte aktualisiert.",
                                "Follow-up answers applied – content refreshed.",
                            ),
                            icon="✅",
                        )
                    else:
                        st.info(
                            tr(
                                "Antworten gespeichert – bitte Feldauswahl oder Interview-Einstellungen prüfen.",
                                "Answers saved – please review field selection or interview settings.",
                            )
                        )
                else:
                    st.info(
                        tr(
                            "Keine Änderungen erkannt – Inhalte bleiben unverändert.",
                            "No changes detected – content remains unchanged.",
                        )
                    )


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
        (tr("Leistungen & Benefits", "Rewards & Benefits"), _step_compensation),
        (tr("Prozess", "Process"), _step_process),
        (tr("Summary", "Summary"), lambda: _step_summary(schema, critical)),
    ]

    st.session_state[StateKeys.WIZARD_STEP_COUNT] = len(steps)
    first_incomplete, _completed_sections = _update_section_progress()
    if st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, False) and (
        first_incomplete is not None
    ):
        st.session_state[StateKeys.STEP] = first_incomplete
    completed_sections = list(
        st.session_state.get(StateKeys.COMPLETED_SECTIONS, [])
    )

    # Headline
    st.markdown("### 🧭 Wizard")

    # Step Navigation (oben)
    def _handle_step_selection(target_index: int) -> None:
        current_index = st.session_state[StateKeys.STEP]
        if target_index == current_index:
            return

        if target_index > current_index:
            max_section = max(target_index - 1, 0)
            missing_before_target = get_missing_critical_fields(
                max_section=max_section
            )
            if missing_before_target:
                next_required_section = min(
                    (
                        _resolve_section_for_field(field)
                        for field in missing_before_target
                    ),
                    default=None,
                )
                if (
                    next_required_section is not None
                    and 0 <= next_required_section < len(steps)
                ):
                    blocking_step_label = steps[next_required_section][0]
                    message = tr(
                        "Bitte fülle zuerst die Pflichtfelder in „{step}“ aus.",
                        "Please complete the required fields in “{step}” first.",
                    ).format(step=blocking_step_label)
                else:
                    message = tr(
                        "Bitte fülle zuerst alle Pflichtfelder in den vorherigen Schritten aus.",
                        "Please complete all required fields in the previous steps before jumping ahead.",
                    )
                st.session_state[StateKeys.STEPPER_WARNING] = message
                return

        st.session_state[StateKeys.STEP] = target_index
        st.rerun()

    render_stepper(
        st.session_state[StateKeys.STEP],
        [label for label, _ in steps],
        on_select=_handle_step_selection,
    )

    _render_confidence_legend()

    warning_message = st.session_state.pop(StateKeys.STEPPER_WARNING, None)
    if warning_message:
        st.warning(warning_message)

    if completed_sections and st.session_state.get("_analyze_attempted"):
        with st.expander(
            tr("✅ Abgeschlossene Abschnitte", "✅ Completed sections"),
            expanded=False,
        ):
            for idx in completed_sections:
                if 0 <= idx < len(steps):
                    section_label, _ = steps[idx]
                    st.markdown(f"- {section_label}")

    # Render current step
    current = st.session_state[StateKeys.STEP]
    _label, renderer = steps[current]

    renderer()

    _apply_pending_scroll_reset()

    # Bottom nav
    section = current - 1
    missing = get_missing_critical_fields(max_section=section) if section >= 1 else []

    if current > 0:
        if current < len(steps) - 1:
            col_prev, col_next = st.columns([1, 1])
            with col_prev:
                if st.button(tr("◀︎ Zurück", "◀︎ Back"), use_container_width=True):
                    prev_step()
                    st.rerun()
            with col_next:
                if st.button(
                    tr("Weiter ▶︎", "Next ▶︎"),
                    type="primary",
                    use_container_width=True,
                    disabled=bool(missing),
                ):
                    next_step()
                    st.rerun()
        else:
            back_col, home_col, donate_col = st.columns([1, 1, 1])
            with back_col:
                if st.button(
                    tr("◀︎ Zurück", "◀︎ Back"),
                    use_container_width=True,
                    key="summary_back",
                ):
                    prev_step()
                    st.rerun()
            with home_col:
                if st.button(
                    tr("🏠 Startseite", "🏠 Home"),
                    key="summary_home",
                    use_container_width=True,
                ):
                    _request_scroll_to_top()
                    reset_state()
                    st.session_state[StateKeys.STEP] = 0
                    st.rerun()
            with donate_col:
                if st.button(
                    tr("❤️ Entwickler unterstützen", "❤️ Donate to the developer"),
                    key="summary_donate",
                    use_container_width=True,
                ):
                    st.session_state["show_donate"] = True

    if current == len(steps) - 1:
        if st.session_state.get("show_donate"):
            st.info(
                tr(
                    "Spendenkonto: DE00 1234 5678 9000 0000 00",
                    "Donation account: DE00 1234 5678 9000 0000 00",
                )
            )

        usage = st.session_state.get(StateKeys.USAGE)
        if usage:
            in_tok, out_tok, total_tok = usage_totals(usage)
            label = tr("Verbrauchte Tokens", "Tokens used")
            summary = f"{label}: {in_tok} + {out_tok} = {total_tok}"
            table = build_usage_markdown(usage)
            if table:
                with st.expander(summary):
                    st.markdown(table)
            else:
                st.caption(summary)
