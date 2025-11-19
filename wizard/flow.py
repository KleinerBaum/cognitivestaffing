# wizard.py — Cognitive Needs Wizard (clean flow, schema-aligned)
from __future__ import annotations

import html
import logging
import hashlib
import json
import textwrap
from dataclasses import dataclass, asdict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
from functools import partial
from pathlib import Path
from enum import StrEnum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
    Final,
    cast,
)
from urllib.parse import urljoin, urlparse

import re
import requests
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit.delta_generator import DeltaGenerator
from streamlit.runtime.uploaded_file_manager import UploadedFile

try:  # pragma: no cover - runtime guard for local/test environments
    from streamlit_sortables import sort_items as _sort_items
except Exception:  # pragma: no cover - gracefully degrade when component runtime missing

    def sort_items(items: list[str] | tuple[str, ...] | Sequence[str], **_: object) -> list[str]:
        """Fallback sorter returning items unchanged when the component is unavailable."""

        if isinstance(items, list):
            return list(items)
        return list(items)

else:
    sort_items = _sort_items

from pydantic import ValidationError
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from utils.i18n import (
    tr,
    EMPLOYMENT_OVERTIME_TOGGLE_HELP,
    EMPLOYMENT_RELOCATION_TOGGLE_HELP,
    EMPLOYMENT_SECURITY_TOGGLE_HELP,
    EMPLOYMENT_SHIFT_TOGGLE_HELP,
    EMPLOYMENT_TRAVEL_TOGGLE_HELP,
    EMPLOYMENT_VISA_TOGGLE_HELP,
    POSITION_CUSTOMER_CONTACT_DETAILS_HINT,
    POSITION_CUSTOMER_CONTACT_TOGGLE_HELP,
)
import config as app_config
from config import set_api_mode, set_responses_allow_tools
from i18n import t as translate_key
from constants.keys import ProfilePaths, StateKeys, UIKeys
from core.errors import ExtractionError
from state import ensure_state
from ingest.extractors import extract_text_from_file, extract_text_from_url
from ingest.reader import clean_structured_document
from ingest.types import ContentBlock, StructuredDocument, build_plain_text_document
from ingest.branding import extract_brand_assets
from ingest.heuristics import apply_basic_fallbacks
from utils.errors import LocalizedMessage, display_error, resolve_message
from utils.url_utils import is_supported_url
from config import REASONING_EFFORT
from config_loader import load_json
from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill
from core.confidence import ConfidenceTier, DEFAULT_AI_TIER
from core.extraction import InvalidExtractionPayload, mark_low_confidence, parse_structured_payload
from core.rules import apply_rules, matches_to_patch, build_rule_metadata
from core.preview import build_prefilled_sections
from llm.client import extract_json
from pages import WIZARD_PAGES, WizardPage
from wizard_router import StepRenderer, WizardContext, WizardRouter
from wizard.followups import followup_has_response
from wizard.interview_step import render_interview_guide_section
from core.esco_utils import lookup_esco_skill
from ._agents import (
    generate_interview_guide_content,
    generate_job_ad_content,
)
from .layout import (
    COMPACT_STEP_STYLE,
    inject_salary_slider_styles,
    _render_autofill_suggestion,
    render_list_text_area,
    render_onboarding_hero,
    render_section_heading,
    render_step_heading,
)
from ._logic import (
    SALARY_SLIDER_MAX,
    SALARY_SLIDER_MIN,
    SALARY_SLIDER_STEP,
    _derive_salary_range_defaults,
    _get_company_logo_bytes,
    _set_company_logo,
    _autofill_was_rejected,
    _update_profile,
    _render_localized_error,
    get_in,
    _normalize_semantic_empty,
    merge_unique_items,
    set_in,
    unique_normalized,
)
from .company_validators import persist_contact_email, persist_primary_city
from .metadata import (
    COMPANY_STEP_INDEX,
    CRITICAL_SECTION_ORDER,
    FIELD_SECTION_MAP,
    PAGE_FOLLOWUP_PREFIXES,
    get_missing_critical_fields,
    resolve_section_for_field,
)
from sidebar.salary import format_salary_range

if TYPE_CHECKING:  # pragma: no cover - typing-only import path
    from streamlit.runtime.scriptrunner import (
        RerunException as StreamlitRerunException,
        StopException as StreamlitStopException,
    )
else:  # pragma: no cover - Streamlit runtime internals are unavailable in tests
    try:
        from streamlit.runtime.scriptrunner import (
            RerunException as StreamlitRerunException,
            StopException as StreamlitStopException,
        )
    except Exception:

        class StreamlitRerunException(RuntimeError):
            """Fallback rerun exception when Streamlit internals are missing."""

        class StreamlitStopException(RuntimeError):
            """Fallback stop exception when Streamlit internals are missing."""


RerunException = StreamlitRerunException
StopException = StreamlitStopException


logger = logging.getLogger(__name__)

_RECOVERABLE_FLOW_ERRORS: tuple[type[Exception], ...] = (
    StreamlitAPIException,
    ValidationError,
    ValueError,
)

LocalizedText = tuple[str, str]


COMPANY_NAME_LABEL: Final[LocalizedText] = ("Unternehmen", "Company")
COMPANY_NAME_PLACEHOLDER: Final[LocalizedText] = (
    "Offiziellen Unternehmensnamen eingeben",
    "Enter the official company name",
)
COMPANY_NAME_HELP: Final[LocalizedText] = (
    "Rechtlicher Name laut Impressum oder Handelsregister.",
    "Legal entity name as listed in the imprint or registry.",
)
COMPANY_CONTACT_NAME_LABEL: Final[LocalizedText] = (
    "HR-Ansprechperson",
    "HR contact person",
)
COMPANY_CONTACT_NAME_PLACEHOLDER: Final[LocalizedText] = (
    "Name der HR-Ansprechperson eingeben",
    "Provide the HR contact's name",
)
COMPANY_CONTACT_EMAIL_LABEL: Final[LocalizedText] = (
    "Kontakt-E-Mail (Unternehmen)",
    "Company contact email",
)
COMPANY_CONTACT_EMAIL_PLACEHOLDER: Final[LocalizedText] = (
    "z. B. talent@unternehmen.de",
    "e.g. talent@company.com",
)
COMPANY_CONTACT_EMAIL_CAPTION: Final[LocalizedText] = (
    "Diese Inbox nutzen wir für Rückfragen, Freigaben und Exportlinks.",
    "We use this inbox for follow-ups, approvals, and export links.",
)
COMPANY_CONTACT_PHONE_LABEL: Final[LocalizedText] = (
    "Kontakt-Telefon",
    "Contact phone",
)
COMPANY_CONTACT_PHONE_PLACEHOLDER: Final[LocalizedText] = (
    "z. B. +49 30 1234567",
    "e.g. +49 30 1234567",
)
PRIMARY_CITY_LABEL: Final[LocalizedText] = (
    "Primärer Standort (Stadt)",
    "Primary location (city)",
)
PRIMARY_CITY_PLACEHOLDER: Final[LocalizedText] = (
    "Stadt für diese Rolle eingeben",
    "Enter the city for this role",
)
PRIMARY_CITY_CAPTION: Final[LocalizedText] = (
    "Steuert Benchmarks, Relocation-Hinweise und Exporttexte.",
    "Feeds benchmarks, relocation copy, and export text.",
)
PRIMARY_COUNTRY_LABEL: Final[LocalizedText] = (
    "Land (Primärstandort)",
    "Country (primary location)",
)
PRIMARY_COUNTRY_PLACEHOLDER: Final[LocalizedText] = (
    "ISO-Code oder Landesname eintragen",
    "Enter the ISO code or country name",
)
CUSTOMER_CONTACT_TOGGLE_LABEL: Final[LocalizedText] = (
    "Regelmäßiger Kundenkontakt?",
    "Customer-facing responsibilities?",
)
ROLE_SUMMARY_LABEL: Final[LocalizedText] = (
    "Rollenbeschreibung",
    "Role summary",
)


class WizardStepKey(StrEnum):
    """Canonical string keys for the wizard navigation order."""

    JOBAD = "jobad"
    COMPANY = "company"
    TEAM = "team"
    ROLE_TASKS = "role_tasks"
    SKILLS = "skills"
    BENEFITS = "benefits"
    INTERVIEW = "interview"
    SUMMARY = "summary"


@dataclass(frozen=True)
class WizardStepDescriptor:
    """Pairs a step key with its renderer."""

    key: WizardStepKey
    renderer: StepRenderer


ONBOARDING_SOURCE_STYLE_KEY: Final[str] = "_onboarding_source_styles_v2"
EXTRACTION_REVIEW_STYLE_KEY: Final[str] = "_extraction_review_styles_v1"
FOLLOWUP_STYLE_KEY: Final[str] = "_followup_styles_v1"

YES_NO_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED),
    str(ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT),
    str(ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP),
    str(ProfilePaths.EMPLOYMENT_OVERTIME_EXPECTED),
    str(ProfilePaths.EMPLOYMENT_SHIFT_WORK),
    str(ProfilePaths.EMPLOYMENT_SECURITY_CLEARANCE_REQUIRED),
    str(ProfilePaths.COMPENSATION_SALARY_PROVIDED),
}

DATE_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.META_TARGET_START_DATE),
    str(ProfilePaths.META_APPLICATION_DEADLINE),
    str(ProfilePaths.EMPLOYMENT_CONTRACT_END),
}

NUMBER_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.POSITION_TEAM_SIZE),
    str(ProfilePaths.POSITION_SUPERVISES),
    str(ProfilePaths.COMPENSATION_SALARY_MIN),
    str(ProfilePaths.COMPENSATION_SALARY_MAX),
    str(ProfilePaths.EMPLOYMENT_TRAVEL_SHARE),
}

LIST_FOLLOWUP_FIELDS: Final[set[str]] = {
    str(ProfilePaths.RESPONSIBILITIES_ITEMS),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_LANGUAGES_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
    str(ProfilePaths.REQUIREMENTS_CERTIFICATIONS),
    str(ProfilePaths.REQUIREMENTS_CERTIFICATES),
    str(ProfilePaths.COMPENSATION_BENEFITS),
}

ESCO_SKILL_ENDPOINT: Final[str] = "https://ec.europa.eu/esco/api/resource/skill"

_SKILL_GROUP_LABELS: Final[dict[str, tuple[str, str]]] = {
    "hard_skills_required": (
        "Muss-Hard-Skill",
        "Must-have hard skill",
    ),
    "hard_skills_optional": (
        "Nice-to-have Hard-Skill",
        "Nice-to-have hard skill",
    ),
    "soft_skills_required": (
        "Muss-Soft-Skill",
        "Must-have soft skill",
    ),
    "soft_skills_optional": (
        "Nice-to-have Soft-Skill",
        "Nice-to-have soft skill",
    ),
    "tools_and_technologies": (
        "Tool & Technologie",
        "Tool & technology",
    ),
    "languages_required": (
        "Pflichtsprache",
        "Required language",
    ),
    "languages_optional": (
        "Optionale Sprache",
        "Optional language",
    ),
    "certificates": (
        "Zertifikat",
        "Certificate",
    ),
}

_SKILL_TYPE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "skill": ("Kompetenz", "Skill"),
    "competence": ("Fähigkeit", "Competence"),
    "knowledge": ("Wissen", "Knowledge"),
    "attitude": ("Einstellung", "Attitude"),
    "tool": ("Tool", "Tool"),
    "language": ("Sprache", "Language"),
}


@dataclass(slots=True)
class SkillInsightEntry:
    """Structured representation for selectable skills in the insights tab."""

    label: str
    source_label: str
    category_key: str
    is_missing: bool


ADD_MORE_PHASES_HINT: Final[LocalizedText] = (
    "Weitere Phasen hinzufügen…",
    "Add more phases…",
)
ADD_MORE_PARTICIPANTS_HINT: Final[LocalizedText] = (
    "Weitere Beteiligte hinzufügen…",
    "Add more participants…",
)
ADD_MORE_INFO_LOOP_PHASES_HINT: Final[LocalizedText] = (
    "Weitere Informationsphasen hinzufügen…",
    "Add more information loop phases…",
)
ADD_MORE_ONBOARDING_HINT: Final[LocalizedText] = (
    "Weitere Onboarding-Schritte hinzufügen…",
    "Add more onboarding steps…",
)
ADD_MORE_SKILL_FOCUS_HINT: Final[LocalizedText] = (
    "Weitere Fokusbereiche hinzufügen…",
    "Add more focus areas…",
)
ADD_MORE_HARD_SKILLS_REQUIRED_HINT: Final[LocalizedText] = (
    "Weitere Muss-Hard-Skills hinzufügen…",
    "Add more must-have hard skills…",
)
ADD_MORE_SOFT_SKILLS_REQUIRED_HINT: Final[LocalizedText] = (
    "Weitere Muss-Soft-Skills hinzufügen…",
    "Add more must-have soft skills…",
)
ADD_MORE_HARD_SKILLS_OPTIONAL_HINT: Final[LocalizedText] = (
    "Weitere Nice-to-have-Hard-Skills hinzufügen…",
    "Add more nice-to-have hard skills…",
)
ADD_MORE_SOFT_SKILLS_OPTIONAL_HINT: Final[LocalizedText] = (
    "Weitere Nice-to-have-Soft-Skills hinzufügen…",
    "Add more nice-to-have soft skills…",
)
ADD_MORE_TOOLS_HINT: Final[LocalizedText] = (
    "Weitere Tools oder Technologien hinzufügen…",
    "Add more tools or technologies…",
)
ADD_MORE_CERTIFICATES_HINT: Final[LocalizedText] = (
    "Weitere Zertifikate hinzufügen…",
    "Add more certificates…",
)
ADD_MORE_REQUIRED_LANGUAGES_HINT: Final[LocalizedText] = (
    "Weitere Pflichtsprachen hinzufügen…",
    "Add more required languages…",
)
ADD_MORE_OPTIONAL_LANGUAGES_HINT: Final[LocalizedText] = (
    "Weitere optionale Sprachen hinzufügen…",
    "Add more optional languages…",
)
ADD_MORE_BENEFITS_HINT: Final[LocalizedText] = (
    "Weitere Benefits hinzufügen…",
    "Add more benefits…",
)
ADD_MORE_BENEFIT_FOCUS_HINT: Final[LocalizedText] = (
    "Weitere Benefit-Schwerpunkte hinzufügen…",
    "Add more benefit focus areas…",
)
ADD_MORE_JOB_AD_FIELDS_HINT: Final[LocalizedText] = (
    "Weitere Inhalte für die Anzeige auswählen…",
    "Select additional job ad sections…",
)

_MISSING = object()

# LLM and Follow-ups
from openai_utils import (
    extract_company_info,
    refine_document,
    summarize_company_page,
)
from core.suggestions import (
    get_benefit_suggestions,
    get_onboarding_suggestions,
    get_responsibility_suggestions,
    get_skill_suggestions,
    get_static_benefit_shortlist,
)
from question_logic import ask_followups, CRITICAL_FIELDS  # nutzt deine neue Definition
from components import widget_factory
from components.stepper import render_stepper as _render_stepper
from wizard.wizard import profile_text_input
from components.chip_multiselect import (
    CHIP_INLINE_VALUE_LIMIT,
    chip_multiselect,
    chip_multiselect_mapped,
    group_chip_options_by_label,
    render_chip_button_grid,
)

render_stepper = _render_stepper
from components.form_fields import text_input_with_state
from components.requirements_insights import render_skill_market_insights
from utils import build_boolean_query, build_boolean_search, seo_optimize
from utils.llm_state import is_llm_available, llm_disabled_message
from utils.normalization import (
    extract_company_size,
    extract_company_size_snippet,
    country_to_iso2,
)
from utils.export import prepare_clean_json, prepare_download_data
from nlp.bias import scan_bias_language
from ingest.heuristics import is_soft_skill
from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    normalize_skills,
    search_occupations,
)
from core.job_ad import (
    JOB_AD_FIELDS,
    JOB_AD_GROUP_LABELS,
    JobAdFieldDefinition,
    resolve_job_ad_field_selection,
    suggest_target_audiences,
)
from constants.style_variants import STYLE_VARIANTS, STYLE_VARIANT_ORDER
from sidebar.salary import resolve_sidebar_benefits

ROOT = Path(__file__).parent
# Onboarding visual reuses the colourful transparent logo that previously
# lived in the sidebar
ONBOARDING_ANIMATION_PATH = ROOT / "images" / "color1_logo_transparent_background.png"


def _guess_mime_type(path: Path) -> str:
    """Return a reasonable MIME type for ``path`` based on its suffix."""

    mapping = {
        ".gif": "image/gif",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    return mapping.get(path.suffix.lower(), "application/octet-stream")


ONBOARDING_ANIMATION_MIME_TYPE = _guess_mime_type(ONBOARDING_ANIMATION_PATH)


def _load_onboarding_animation_bytes() -> bytes | None:
    """Read the onboarding hero animation from disk on demand."""

    try:
        return ONBOARDING_ANIMATION_PATH.read_bytes()
    except FileNotFoundError:
        return None


def _render_onboarding_hero() -> None:
    """Render the onboarding hero with freshly loaded media bytes."""

    animation_bytes = _load_onboarding_animation_bytes()
    render_onboarding_hero(animation_bytes, mime_type=ONBOARDING_ANIMATION_MIME_TYPE)


ensure_state()

WIZARD_TITLE = "Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool"

PAGE_LOOKUP: dict[str, WizardPage] = {page.key: page for page in WIZARD_PAGES}

MAX_INLINE_VALUE_CHARS = CHIP_INLINE_VALUE_LIMIT

INTRO_TONES: tuple[str, ...] = ("pragmatic", "formal", "casual")
DEFAULT_INTRO_TONE = INTRO_TONES[0]


def _persist_branding_asset_from_state(key: str) -> None:
    """Store the uploaded branding asset in session state."""

    value = st.session_state.get(key)
    if isinstance(value, UploadedFile):
        try:
            data = value.getvalue()
        except Exception:  # pragma: no cover - streamlit guard
            return
        if not data:
            st.session_state.pop(StateKeys.COMPANY_BRANDING_ASSET, None)
            return
        st.session_state[StateKeys.COMPANY_BRANDING_ASSET] = {
            "name": getattr(value, "name", ""),
            "type": getattr(value, "type", ""),
            "data": bytes(data),
        }
        return

    if value is None:
        st.session_state.pop(StateKeys.COMPANY_BRANDING_ASSET, None)


_SKILL_IDENTIFIER_PATTERN = re.compile(r"^(?:hard|soft):[0-9a-f]{12}$")
_SKILL_ID_ATTR_PATTERN = re.compile(r"data-skill-id=['\"]([^'\"]+)['\"]")

# Backwards compatibility for tests monkeypatching legacy helpers
_generate_job_ad_content = generate_job_ad_content
_generate_interview_guide_content = generate_interview_guide_content
_inject_salary_slider_styles = inject_salary_slider_styles

WIZARD_TRACER = trace.get_tracer(__name__)


def _extract_city_from_text(raw: str) -> str | None:
    """Extract a likely city name from ``raw`` text."""

    if not raw:
        return None
    parts = re.split(r"[,/|;\-]\s*", raw)
    for part in parts:
        candidate = part.strip()
        if candidate and any(char.isalpha() for char in candidate):
            return candidate
    cleaned = raw.strip()
    return cleaned or None


def _profile_city(profile: Mapping[str, Any]) -> str | None:
    """Return the most relevant city for ``profile`` if available."""

    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    primary_city = str(location.get("primary_city") or "").strip()
    if primary_city:
        return primary_city
    company = profile.get("company", {}) if isinstance(profile, Mapping) else {}
    return _extract_city_from_text(str(company.get("hq_location") or ""))


def _string_or_empty(value: Any) -> str:
    """Return ``value`` as a string, normalising ``None`` to an empty string."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


_LOCAL_BENEFIT_COUNTRY_PRESETS: dict[str, list[tuple[str, str]]] = {
    "DE": [
        (
            "Zuschuss zum Deutschlandticket oder regionalen ÖPNV-Abo",
            "Subsidy for the Deutschlandticket or local public transport pass",
        ),
        (
            "Mitgliedschaft im {city}-Fußball- oder Sportverein",
            "Membership at the {city} football or sports club",
        ),
    ],
    "AT": [
        (
            "Klimaticket- oder ÖPNV-Zuschuss für {city}",
            "Klimaticket or public transport subsidy around {city}",
        ),
    ],
    "CH": [
        (
            "SBB-Halbtax- oder Regionalabo-Zuschuss",
            "SBB half-fare or regional travel pass subsidy",
        ),
        (
            "Mitgliedschaft in einem regionalen Sportverein in {city}",
            "Membership in a regional sports club in {city}",
        ),
    ],
    "US": [
        (
            "Corporate-Mitgliedschaft in Fitnessstudios und Sportvereinen in {city}",
            "Corporate membership for gyms and sports clubs in {city}",
        ),
        (
            "Volunteer Day zur Unterstützung lokaler Projekte in {city}",
            "Volunteer day to support community projects in {city}",
        ),
    ],
    "GB": [
        (
            "Unterstützung für lokale Season Tickets im ÖPNV",
            "Support for local public transport season tickets",
        ),
        (
            "Mitgliedschaft im {city} Football Club Supporters Scheme",
            "Membership in the {city} football club supporters scheme",
        ),
    ],
}

_LOCAL_BENEFIT_FALLBACKS: list[tuple[str, str]] = [
    (
        "Gutscheine für lokale Cafés und Coworking-Spaces in {city}",
        "Vouchers for local cafés and co-working spaces in {city}",
    ),
    (
        "Teilnahme an regionalen Meetups & Fachkonferenzen in {city}",
        "Participation in regional meetups and industry events in {city}",
    ),
    (
        "Unterstützte Ehrenamtstage für Initiativen in {city}",
        "Sponsored volunteer days for initiatives in {city}",
    ),
]


def _generate_local_benefits(profile: Mapping[str, Any], *, lang: str) -> list[str]:
    """Return locally flavoured benefit ideas based on profile context."""

    compensation = profile.get("compensation", {}) if isinstance(profile, Mapping) else {}
    existing_values = unique_normalized(str(item) for item in (compensation.get("benefits", []) or []))
    existing = {value.casefold() for value in existing_values}
    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    country_raw = str(location.get("country") or "").strip()
    iso_country = country_to_iso2(country_raw) if country_raw else None
    city = _profile_city(profile)
    city_placeholder = city or tr("der Region", "the region", lang=lang)

    templates: list[tuple[str, str]] = []
    if iso_country and iso_country in _LOCAL_BENEFIT_COUNTRY_PRESETS:
        templates.extend(_LOCAL_BENEFIT_COUNTRY_PRESETS[iso_country])
    templates.extend(_LOCAL_BENEFIT_FALLBACKS)

    suggestions: list[str] = []
    seen: set[str] = set()
    for de_text, en_text in templates:
        text = tr(de_text, en_text, lang=lang)
        if "{city}" in text:
            text = text.format(city=city_placeholder)
        normalized = text.strip()
        if not normalized:
            continue
        marker = normalized.casefold()
        if marker in seen or marker in existing:
            continue
        seen.add(marker)
        suggestions.append(normalized)
    normalized_suggestions = unique_normalized(suggestions)
    return normalized_suggestions[:5]


T = TypeVar("T")


_SKILL_FOCUS_PRESETS: dict[str, list[str]] = {
    "de": [
        "Cloud & Infrastruktur",
        "Daten & Analytik",
        "Cybersecurity",
        "KI & Automatisierung",
        "Kundenerlebnis",
        "Leadership & Coaching",
    ],
    "en": [
        "Cloud & Infrastructure",
        "Data & Analytics",
        "Cybersecurity",
        "AI & Automation",
        "Customer Experience",
        "Leadership & Coaching",
    ],
}

_SUGGESTION_GROUP_LABEL_KEYS: dict[str, str] = {
    "llm": "suggestion_group_llm",
    "esco": "suggestion_group_esco_skill",
    "esco_skill": "suggestion_group_esco_skill",
    "esco_missing": "suggestion_group_esco_missing_skill",
    "esco_knowledge": "suggestion_group_esco_knowledge",
    "esco_competence": "suggestion_group_esco_competence",
    "esco_tools": "suggestion_group_esco_tools",
    "esco_certificates": "suggestion_group_esco_certificates",
    "esco_missing_skill": "suggestion_group_esco_missing_skill",
    "esco_missing_knowledge": "suggestion_group_esco_missing_knowledge",
    "esco_missing_competence": "suggestion_group_esco_missing_competence",
    "esco_missing_tools": "suggestion_group_esco_missing_tools",
    "esco_missing_certificates": "suggestion_group_esco_missing_certificates",
}

_BENEFIT_FOCUS_PRESETS: dict[str, list[str]] = {
    "de": [
        "Gesundheit & Wohlbefinden",
        "Flexible Arbeitsmodelle",
        "Weiterbildung & Budget",
        "Mobilität & Pendeln",
        "Familie & Care",
        "Finanzielle Zusatzleistungen",
    ],
    "en": [
        "Health & Wellbeing",
        "Flexible Work Models",
        "Learning & Development Budget",
        "Mobility & Commuting",
        "Family & Care Support",
        "Financial Extras",
    ],
}


SkillCategory = Literal["hard", "soft"]
SkillSource = Literal["auto", "ai", "esco"]
SkillContainerType = Literal[
    "source_extracted",
    "source_ai",
    "source_esco",
    "target_must",
    "target_nice",
]


class SkillBubbleMeta(TypedDict):
    """Metadata used to track drag-and-drop skill bubbles."""

    label: str
    category: SkillCategory
    source: SkillSource


_SKILL_CONTAINER_ORDER: tuple[SkillContainerType, ...] = (
    "source_extracted",
    "source_ai",
    "source_esco",
    "target_must",
    "target_nice",
)

_SKILL_BOARD_STYLE = """
.sortable-component {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem;
    padding: 1.35rem;
    border-radius: 1.75rem;
    background: radial-gradient(circle at 12% -15%, rgba(63, 180, 202, 0.42), rgba(6, 14, 26, 0.94));
    border: 1px solid rgba(87, 182, 255, 0.28);
    box-shadow: 0 42px 86px rgba(2, 8, 20, 0.55);
    overflow: visible;
    backdrop-filter: blur(18px) saturate(140%);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
}

.sortable-container {
    flex: 1 1 clamp(260px, 48%, 520px);
    background: linear-gradient(165deg, rgba(7, 20, 36, 0.96), rgba(18, 42, 62, 0.82));
    color: rgba(243, 249, 255, 0.96);
    border-radius: 1.35rem;
    border: 1px solid rgba(87, 182, 255, 0.28);
    padding: 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    box-shadow: 0 34px 64px rgba(2, 10, 24, 0.48);
    position: relative;
    overflow: hidden;
    isolation: isolate;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.sortable-container::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(140deg, rgba(47, 216, 197, 0.18), rgba(137, 170, 255, 0.14));
    opacity: 0;
    transition: opacity 0.25s ease;
    pointer-events: none;
    z-index: -1;
}

.sortable-container:hover {
    transform: translateY(-4px);
    box-shadow: 0 42px 78px rgba(2, 12, 26, 0.52);
}

.sortable-container:hover::before {
    opacity: 1;
}

.sortable-component > div:nth-child(1) {
    flex: 1 1 100%;
    order: 0;
    background: linear-gradient(150deg, rgba(19, 84, 128, 0.9), rgba(41, 118, 162, 0.78));
    color: #f5fbff;
}

.sortable-component > div:nth-child(2),
.sortable-component > div:nth-child(3) {
    flex: 1 1 calc(50% - 0.75rem);
    order: 1;
}

.sortable-component > div:nth-child(2) {
    background: linear-gradient(150deg, rgba(15, 95, 88, 0.9), rgba(29, 140, 124, 0.78));
    color: #f3fffb;
}

.sortable-component > div:nth-child(3) {
    background: linear-gradient(150deg, rgba(21, 82, 134, 0.88), rgba(44, 128, 176, 0.78));
    color: #f2fbff;
}

.sortable-component > div:nth-child(4),
.sortable-component > div:nth-child(5) {
    flex: 1 1 calc(50% - 0.75rem);
    order: 2;
}

.sortable-component > div:nth-child(4) {
    background: linear-gradient(150deg, rgba(98, 32, 78, 0.92), rgba(162, 58, 112, 0.8));
    color: #fff6fb;
}

.sortable-component > div:nth-child(5) {
    background: linear-gradient(150deg, rgba(40, 54, 124, 0.9), rgba(33, 104, 148, 0.76));
    color: #f4fbff;
}

.sortable-container-header {
    font-weight: 600;
    font-size: 1.05rem;
    letter-spacing: 0.01em;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.sortable-container-header::after {
    content: "";
    flex: 1 1 auto;
    height: 1px;
    margin-left: 0.5rem;
    background: rgba(226, 232, 240, 0.4);
}

.sortable-container-body {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    min-height: 3.5rem;
}

.sortable-component > div:nth-child(1) .sortable-container-header::after,
.sortable-component > div:nth-child(2) .sortable-container-header::after,
.sortable-component > div:nth-child(3) .sortable-container-header::after,
.sortable-component > div:nth-child(4) .sortable-container-header::after,
.sortable-component > div:nth-child(5) .sortable-container-header::after {
    background: rgba(243, 247, 255, 0.55);
}

.sortable-component > div:nth-child(1) .sortable-container-body,
.sortable-component > div:nth-child(2) .sortable-container-body,
.sortable-component > div:nth-child(3) .sortable-container-body,
.sortable-component > div:nth-child(4) .sortable-container-body,
.sortable-component > div:nth-child(5) .sortable-container-body {
    padding-bottom: 0.25rem;
}

.sortable-item {
    background: linear-gradient(135deg, rgba(251, 254, 255, 0.9), rgba(223, 244, 249, 0.74));
    color: #082235;
    padding: 0.42rem 0.92rem;
    border-radius: 999px;
    border: 1px solid rgba(87, 182, 255, 0.32);
    font-size: 0.9rem;
    font-weight: 500;
    box-shadow: 0 16px 28px rgba(6, 20, 36, 0.24);
    cursor: grab;
    white-space: nowrap;
    max-width: 20ch;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: transform 0.2s ease, box-shadow 0.2s ease, max-width 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    position: relative;
}

.sortable-item .skill-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}

.sortable-item[data-source]::after {
    content: attr(data-source-short);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-left: 0.35rem;
    padding: 0.08rem 0.45rem;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    border-radius: 999px;
    background: rgba(9, 28, 42, 0.32);
    color: #031523;
    text-transform: uppercase;
    white-space: nowrap;
}

.sortable-item[data-source="ai"]::after {
    background: rgba(87, 182, 255, 0.78);
    color: #06233c;
}

.sortable-item[data-source="esco"]::after {
    background: rgba(245, 178, 107, 0.82);
    color: #3b220b;
}

.sortable-component > div:nth-child(1) .sortable-item,
.sortable-component > div:nth-child(2) .sortable-item,
.sortable-component > div:nth-child(3) .sortable-item {
    background: rgba(255, 255, 255, 0.16);
    color: #f4fbff;
    border-color: rgba(244, 251, 255, 0.34);
}

.sortable-item:hover {
    max-width: min(38ch, 100%);
    box-shadow: 0 22px 40px rgba(4, 14, 30, 0.32);
    transform: translateY(-1px);
    z-index: 3;
}

.sortable-item.dragging {
    opacity: 0.82;
    cursor: grabbing;
    box-shadow: 0 24px 44px rgba(3, 12, 26, 0.34);
}

@media (max-width: 1180px) {
    .sortable-container {
        flex: 1 1 calc(50% - 1.25rem);
    }
}

@media (max-width: 820px) {
    .sortable-component {
        gap: 1rem;
        padding: 1.1rem;
    }
}

@media (max-width: 640px) {
    .sortable-container {
        flex: 1 1 100%;
    }
}
"""


_SKILL_BOARD_STYLE_KEY = "ui.requirements.skill_board_style"


def _ensure_skill_board_style() -> None:
    """Inject one-time styles for the drag-and-drop skill board."""

    if st.session_state.get(_SKILL_BOARD_STYLE_KEY):
        return

    st.session_state[_SKILL_BOARD_STYLE_KEY] = True
    st.markdown(f"<style>{_SKILL_BOARD_STYLE}</style>", unsafe_allow_html=True)


def _skill_source_label(source: SkillSource, lang: str | None = None) -> str:
    """Return a localized label for the given skill source."""

    lang_code = lang or st.session_state.get("lang", "de")
    source_labels: dict[SkillSource, str] = {
        "auto": tr("Auto", "Auto", lang=lang_code),
        "ai": tr("KI", "AI", lang=lang_code),
        "esco": tr("ESCO", "ESCO", lang=lang_code),
    }
    return source_labels[source]


def _infer_skill_category(label: str) -> SkillCategory:
    """Infer whether a skill should be treated as hard or soft."""

    return "soft" if is_soft_skill(label) else "hard"


def _skill_board_labels(lang: str | None = None) -> dict[SkillContainerType, str]:
    """Return localized column headers for the skill board."""

    lang_code = lang or st.session_state.get("lang", "de")
    return {
        "source_extracted": tr(
            "Extrahierte Anforderungen",
            "Extracted requirements",
            lang=lang_code,
        ),
        "source_ai": tr(
            "KI-Vorschläge",
            "AI suggestions",
            lang=lang_code,
        ),
        "source_esco": tr(
            "ESCO-Essentials",
            "ESCO essentials",
            lang=lang_code,
        ),
        "target_must": tr(
            "Muss-Anforderungen",
            "Must-have requirements",
            lang=lang_code,
        ),
        "target_nice": tr("Nice-to-have", "Nice-to-have", lang=lang_code),
    }


def _build_skill_identifier(label: str, category: SkillCategory) -> str:
    """Return a stable identifier for the given ``label`` and ``category``."""

    normalized = html.unescape(label).strip().casefold()
    payload = f"{category}::{normalized}".encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:12]
    return f"{category}:{digest}"


def _looks_like_skill_identifier(value: str) -> bool:
    """Return ``True`` if ``value`` resembles a generated skill identifier."""

    return bool(_SKILL_IDENTIFIER_PATTERN.fullmatch(value.strip()))


def _extract_skill_identifier(raw: str) -> str | None:
    """Extract an identifier from markup or legacy payloads."""

    trimmed = str(raw).strip()
    if not trimmed:
        return None
    if _looks_like_skill_identifier(trimmed):
        return trimmed
    match = _SKILL_ID_ATTR_PATTERN.search(trimmed)
    if match:
        return match.group(1).strip()
    return None


def _strip_legacy_skill_label(raw: str) -> str:
    """Remove formatting artefacts from stored skill labels."""

    text = str(raw)
    if "⟮" in text:
        text = text.split("⟮", 1)[0]
    # Drop any HTML artefacts from sortable markup
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _skill_source_badge(source: SkillSource, lang: str | None = None) -> str:
    """Return a compact badge label for ``source``."""

    lang_code = lang or st.session_state.get("lang", "de")
    short_labels: dict[SkillSource, str] = {
        "auto": tr("Doc", "Doc", lang=lang_code),
        "ai": tr("KI", "AI", lang=lang_code),
        "esco": tr("ESCO", "ESCO", lang=lang_code),
    }
    return short_labels[source]


def _skill_chip_markup(
    identifier: str,
    info: SkillBubbleMeta,
    *,
    lang: str,
) -> str:
    """Return HTML markup used to render a draggable skill chip."""

    label = html.escape(info["label"])
    source = info["source"]
    source_label = html.escape(_skill_source_label(source, lang=lang))
    source_short = html.escape(_skill_source_badge(source, lang=lang))
    return (
        "<span class='skill-chip'"
        f" data-skill-id='{identifier}'"
        f" data-source='{source}'"
        f" data-source-label='{source_label}'"
        f" data-source-short='{source_short}'"
        f" title='{source_label}'>"
        f"{label}"  # Label remains clean; badge is injected via CSS.
        "</span>"
    )


_CONTAINER_SOURCE_DEFAULT: dict[SkillContainerType, SkillSource] = {
    "source_extracted": "auto",
    "source_ai": "ai",
    "source_esco": "esco",
    "target_must": "auto",
    "target_nice": "auto",
}


def _register_skill_bubble(
    meta: dict[str, SkillBubbleMeta],
    label: str,
    *,
    category: SkillCategory,
    source: SkillSource,
) -> str:
    """Create or update display metadata for a draggable skill bubble."""

    cleaned_label = label.strip()
    identifier = _build_skill_identifier(cleaned_label, category)
    existing = meta.get(identifier)
    if existing:
        existing["label"] = cleaned_label
        source_priority = {"auto": 0, "ai": 1, "esco": 2}
        if source_priority[source] > source_priority[existing["source"]]:
            existing["source"] = source
        return identifier
    meta[identifier] = {
        "label": cleaned_label,
        "category": category,
        "source": source,
    }
    return identifier


def _find_existing_display(
    meta: Mapping[str, SkillBubbleMeta],
    *,
    label: str,
    category: SkillCategory,
    source: SkillSource | None = None,
) -> str | None:
    """Return the display string for an existing bubble with the same label."""

    needle = label.strip().casefold()
    for identifier, info in meta.items():
        if info["category"] != category:
            continue
        if source is not None and info["source"] != source:
            continue
        if info["label"].strip().casefold() == needle:
            return identifier
    return None


def _resolve_skill_identifier(
    raw_item: str,
    *,
    meta: dict[str, SkillBubbleMeta],
    legacy_map: dict[str, str],
    container: SkillContainerType,
) -> str | None:
    """Normalise persisted ``raw_item`` values to the current identifier scheme."""

    trimmed = str(raw_item).strip()
    if not trimmed:
        return None

    direct_identifier = _extract_skill_identifier(trimmed)
    if direct_identifier and direct_identifier in meta:
        legacy_map.setdefault(direct_identifier, direct_identifier)
        return direct_identifier

    if trimmed in meta:
        legacy_map.setdefault(trimmed, trimmed)
        return trimmed

    if direct_identifier:
        mapped_identifier = legacy_map.get(direct_identifier)
        if mapped_identifier and mapped_identifier in meta:
            return mapped_identifier

    lookup_candidates = [trimmed, _strip_legacy_skill_label(trimmed)]
    for candidate in lookup_candidates:
        mapped = legacy_map.get(candidate)
        if mapped and mapped in meta:
            return mapped

    label = _strip_legacy_skill_label(trimmed)
    if not label:
        return None

    needle = label.casefold()
    for identifier, info in meta.items():
        if info["label"].casefold() == needle:
            legacy_map.setdefault(trimmed, identifier)
            legacy_map.setdefault(label, identifier)
            return identifier

    source = _CONTAINER_SOURCE_DEFAULT.get(container, "auto")
    category = _infer_skill_category(label)
    identifier = _register_skill_bubble(meta, label, category=category, source=source)
    legacy_map.setdefault(trimmed, identifier)
    legacy_map.setdefault(label, identifier)
    return identifier


def _render_skill_board(
    requirements: dict[str, Any],
    *,
    llm_suggestions: Mapping[str, Mapping[str, Sequence[str]]] | None,
    esco_skills: Sequence[str] | None,
    missing_esco_skills: Sequence[str] | None,
) -> None:
    """Render the combined drag-and-drop board for skill selection."""

    _ensure_skill_board_style()

    render_step_heading(
        tr("Anforderungen & Qualifikationen", "Requirements & qualifications"),
        tr(
            "Lege Skills, Tools und Zertifikate fest. KI- und Marktinputs helfen bei der Priorisierung.",
            "Define skills, tools, and certificates. Let AI and market insights guide the prioritisation.",
        ),
    )

    esco_opted_in = bool(st.session_state.get(StateKeys.REQUIREMENTS_ESCO_OPT_IN))
    llm_available = any(
        bool(groups) and any(group_values for group_values in groups.values())
        for groups in (llm_suggestions or {}).values()
    )
    lang_code = st.session_state.get("lang", "de")
    labels = _skill_board_labels(lang_code)
    esco_candidates = unique_normalized(esco_skills if esco_opted_in else [])
    normalized_missing = unique_normalized(missing_esco_skills if esco_opted_in else [])

    stored_state = st.session_state.get(StateKeys.SKILL_BOARD_STATE)
    board_state: dict[SkillContainerType, list[str]] = {container: [] for container in _SKILL_CONTAINER_ORDER}
    if isinstance(stored_state, Mapping):
        legacy_mapping: dict[str, SkillContainerType] = {
            "target_must": "target_must",
            "target_nice": "target_nice",
            "source_auto": "source_extracted",
            "source_extracted": "source_extracted",
            "source_ai": "source_ai",
            "source_esco": "source_esco",
            "source_suggestions": "source_ai",
        }
        for raw_container, raw_items in stored_state.items():
            target_container = legacy_mapping.get(str(raw_container))
            if target_container is None:
                continue
            if not isinstance(raw_items, Collection):
                continue
            for raw_item in raw_items:
                if not isinstance(raw_item, str):
                    continue
                cleaned_item = raw_item.strip()
                if not cleaned_item:
                    continue
                board_state[target_container].append(cleaned_item)

    if not esco_opted_in:
        board_state["source_esco"] = []

    stored_meta = st.session_state.get(StateKeys.SKILL_BOARD_META)
    meta: dict[str, SkillBubbleMeta] = {}
    legacy_identifier_map: dict[str, str] = {}
    if isinstance(stored_meta, Mapping):
        for key, raw_info in stored_meta.items():
            if not isinstance(raw_info, Mapping):
                continue
            label_value = str(raw_info.get("label", "")).strip()
            raw_category = raw_info.get("category", "hard")
            category_value: SkillCategory = (
                cast(SkillCategory, raw_category) if raw_category in {"hard", "soft"} else "hard"
            )
            raw_source = raw_info.get("source", "auto")
            source_value: SkillSource = (
                cast(SkillSource, raw_source) if raw_source in {"auto", "ai", "esco"} else "auto"
            )
            candidate_identifier = str(raw_info.get("identifier", "")).strip()
            identifier: str
            if candidate_identifier and _looks_like_skill_identifier(candidate_identifier):
                identifier = candidate_identifier
            elif isinstance(key, str) and _looks_like_skill_identifier(key):
                identifier = key.strip()
            else:
                fallback_seed = label_value or str(key)
                identifier = _build_skill_identifier(fallback_seed, category_value)
            meta[identifier] = {
                "label": label_value,
                "category": category_value,
                "source": source_value,
            }
            legacy_identifier_map[str(key)] = identifier
            legacy_identifier_map[identifier] = identifier
            if label_value:
                legacy_identifier_map[label_value] = identifier
                source_label = _skill_source_label(source_value, lang=lang_code)
                legacy_identifier_map[f"{label_value} ⟮{source_label}⟯"] = identifier

    for container in _SKILL_CONTAINER_ORDER:
        normalised_items: list[str] = []
        for raw_item in board_state.get(container, []):
            if not isinstance(raw_item, str):
                continue
            resolved_identifier: str | None = _resolve_skill_identifier(
                raw_item,
                meta=meta,
                legacy_map=legacy_identifier_map,
                container=container,
            )
            if resolved_identifier is None or resolved_identifier in normalised_items:
                continue
            normalised_items.append(resolved_identifier)
        board_state[container] = normalised_items

    for identifier, info in meta.items():
        legacy_identifier_map.setdefault(identifier, identifier)
        label_value = info.get("label", "")
        if not label_value:
            continue
        legacy_identifier_map.setdefault(label_value, identifier)
        source_label = _skill_source_label(info.get("source", "auto"), lang=lang_code)
        legacy_identifier_map.setdefault(f"{label_value} ⟮{source_label}⟯", identifier)

    source_for_container: dict[SkillSource, SkillContainerType] = {
        "auto": "source_extracted",
        "ai": "source_ai",
        "esco": "source_esco",
    }

    for container in ("source_extracted", "source_ai", "source_esco"):
        items = list(board_state.get(container, []))
        board_state[container] = []
        for item in items:
            item_meta = meta.get(item)
            if not item_meta:
                target_bucket = container
            else:
                target_bucket = source_for_container.get(item_meta["source"], "source_extracted")
            if target_bucket not in board_state:
                board_state[target_bucket] = []
            if item not in board_state[target_bucket]:
                board_state[target_bucket].append(item)

    def _is_present(item: str) -> bool:
        return any(item in bucket for bucket in board_state.values())

    def _move_to_container(item: str, container: SkillContainerType) -> None:
        for bucket in board_state.values():
            if item in bucket:
                bucket.remove(item)
        board_state[container].append(item)

    def _add_if_absent(item: str, container: SkillContainerType) -> None:
        if _is_present(item):
            return
        board_state[container].append(item)

    hard_required = requirements.get("hard_skills_required", []) or []
    soft_required = requirements.get("soft_skills_required", []) or []
    hard_optional = requirements.get("hard_skills_optional", []) or []
    soft_optional = requirements.get("soft_skills_optional", []) or []

    for value in hard_required:
        if not isinstance(value, str):
            continue
        display = _find_existing_display(
            meta,
            label=value,
            category="hard",
        )
        if display is None:
            display = _register_skill_bubble(
                meta,
                value,
                category="hard",
                source="auto",
            )
        _move_to_container(display, "target_must")

    for value in soft_required:
        if not isinstance(value, str):
            continue
        display = _find_existing_display(
            meta,
            label=value,
            category="soft",
        )
        if display is None:
            display = _register_skill_bubble(
                meta,
                value,
                category="soft",
                source="auto",
            )
        _move_to_container(display, "target_must")

    for value in hard_optional:
        if not isinstance(value, str):
            continue
        display = _find_existing_display(
            meta,
            label=value,
            category="hard",
        )
        if display is None:
            display = _register_skill_bubble(
                meta,
                value,
                category="hard",
                source="auto",
            )
        _move_to_container(display, "target_nice")

    for value in soft_optional:
        if not isinstance(value, str):
            continue
        display = _find_existing_display(
            meta,
            label=value,
            category="soft",
        )
        if display is None:
            display = _register_skill_bubble(
                meta,
                value,
                category="soft",
                source="auto",
            )
        _move_to_container(display, "target_nice")

    extracted_field_map: tuple[tuple[str, SkillCategory], ...] = (
        ("hard_skills_required", "hard"),
        ("soft_skills_required", "soft"),
        ("hard_skills_optional", "hard"),
        ("soft_skills_optional", "soft"),
        ("tools_and_technologies", "hard"),
        ("languages_required", "hard"),
        ("languages_optional", "hard"),
        ("certificates", "hard"),
        ("certifications", "hard"),
    )

    for field_name, category in extracted_field_map:
        raw_values = requirements.get(field_name, []) or []
        if not isinstance(raw_values, Collection):
            continue
        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                continue
            cleaned = raw_value.strip()
            if not cleaned:
                continue
            display = _find_existing_display(
                meta,
                label=cleaned,
                category=category,
                source="auto",
            )
            if display is None:
                display = _register_skill_bubble(
                    meta,
                    cleaned,
                    category=category,
                    source="auto",
                )
            _add_if_absent(display, "source_extracted")

    if llm_suggestions:
        for bucket_key, grouped_values in llm_suggestions.items():
            if bucket_key not in {"hard_skills", "soft_skills"}:
                continue
            llm_category: SkillCategory = "hard" if bucket_key == "hard_skills" else "soft"
            for values in grouped_values.values():
                for raw in values or []:
                    cleaned = str(raw or "").strip()
                    if not cleaned:
                        continue
                    display = _find_existing_display(
                        meta,
                        label=cleaned,
                        category=llm_category,
                    )
                    if display is None:
                        display = _register_skill_bubble(
                            meta,
                            cleaned,
                            category=llm_category,
                            source="ai",
                        )
                    _add_if_absent(display, "source_ai")

    if esco_opted_in:
        for cleaned in esco_candidates:
            esco_category: SkillCategory = _infer_skill_category(cleaned)
            display = _find_existing_display(
                meta,
                label=cleaned,
                category=esco_category,
            )
            if display is None:
                alternate: SkillCategory = "soft" if esco_category == "hard" else "hard"
                alt_display = _find_existing_display(
                    meta,
                    label=cleaned,
                    category=alternate,
                )
                if alt_display is not None:
                    display = alt_display
                    category = alternate
            if display is None:
                display = _register_skill_bubble(
                    meta,
                    cleaned,
                    category=category,
                    source="esco",
                )
            _add_if_absent(display, "source_esco")

    st.header(tr("Skill-Board", "Skill board", lang=lang_code))
    st.subheader(
        tr(
            "Alle Skills an einem Ort organisieren",
            "Organise every skill in one place",
            lang=lang_code,
        )
    )
    info_lines = [
        tr(
            "Hier landen alle Pflicht-, Nice-to-have- und vorgeschlagenen Skills.",
            "All must-have, nice-to-have, and suggested skills gather here.",
            lang=lang_code,
        ),
        tr(
            "Sortiere sie in die passenden Bereiche, um dein Skill-Set zu definieren.",
            "Place each one into the right bucket to define your skill mix.",
            lang=lang_code,
        ),
        tr(
            "Jede Auswahl beeinflusst Vergütungsspannen und die Verfügbarkeit geeigneter Talente.",
            "Every selection affects salary expectations and the availability of qualified talent.",
            lang=lang_code,
        ),
    ]
    if esco_opted_in:
        info_lines.append(
            tr(
                "ESCO markiert fehlende Essentials separat – schiebe sie in Muss oder Nice-to-have.",
                "ESCO highlights missing essentials separately – drag them into Must-have or Nice-to-have.",
                lang=lang_code,
            )
        )
    st.markdown("  \n".join(info_lines))

    chip_markup: dict[str, str] = {
        identifier: _skill_chip_markup(identifier, bubble_meta, lang=lang_code)
        for identifier, bubble_meta in meta.items()
    }

    board_payload = []
    for container in _SKILL_CONTAINER_ORDER:
        rendered_items: list[str] = []
        for identifier in board_state.get(container, []):
            markup = chip_markup.get(identifier)
            if markup is None:
                bubble_meta = meta.get(identifier)
                if bubble_meta:
                    markup = _skill_chip_markup(identifier, bubble_meta, lang=lang_code)
                    chip_markup[identifier] = markup
                else:
                    markup = html.escape(identifier)
            legacy_identifier_map.setdefault(markup, identifier)
            rendered_items.append(markup)
        board_payload.append(
            {
                "header": labels[container],
                "items": rendered_items,
            }
        )

    sorted_items = sort_items(
        board_payload,
        multi_containers=True,
        direction="horizontal",
        custom_style=_SKILL_BOARD_STYLE,
        key="requirements_skill_board",
    )

    header_to_type = {labels[container]: container for container in _SKILL_CONTAINER_ORDER}
    updated_state: dict[SkillContainerType, list[str]] = {container: [] for container in _SKILL_CONTAINER_ORDER}

    for container in sorted_items:
        header = container.get("header")
        container_type = header_to_type.get(str(header))
        if container_type is None:
            continue
        cleaned_items: list[str] = []
        for raw_item in container.get("items", []) or []:
            if not isinstance(raw_item, str):
                continue
            cleaned_identifier: str | None = _resolve_skill_identifier(
                raw_item,
                meta=meta,
                legacy_map=legacy_identifier_map,
                container=container_type,
            )
            if cleaned_identifier is None or cleaned_identifier in cleaned_items:
                continue
            cleaned_items.append(cleaned_identifier)
        updated_state[container_type] = cleaned_items

    board_state = updated_state

    active_items = {item for bucket in board_state.values() for item in bucket if isinstance(item, str)}
    meta = {key: value for key, value in meta.items() if key in active_items}

    st.session_state[StateKeys.SKILL_BOARD_STATE] = board_state
    st.session_state[StateKeys.SKILL_BOARD_META] = meta

    filtered_missing: list[str] = []
    if normalized_missing:
        present_labels = {info["label"].casefold() for info in meta.values()}
        filtered_missing = [skill for skill in normalized_missing if skill.casefold() not in present_labels]

    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = filtered_missing

    if filtered_missing:
        st.warning(
            tr(
                "ESCO empfiehlt weiterhin essenzielle Skills: {skills}",
                "ESCO still recommends essential skills: {skills}",
                lang=lang_code,
            ).format(skills=", ".join(filtered_missing))
        )

    def _join_sources(parts: Sequence[str], conjunction: str) -> str:
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return f"{parts[0]} {conjunction} {parts[1]}"
        return f"{', '.join(parts[:-1])} {conjunction} {parts[-1]}"

    source_parts_de: list[str] = ["„Extrahierte Anforderungen“"]
    source_parts_en: list[str] = ["“Extracted requirements”"]
    if llm_available:
        source_parts_de.append("„KI-Vorschläge“")
        source_parts_en.append("“AI suggestions”")
    if esco_opted_in:
        source_parts_de.append("„ESCO-Essentials“")
        source_parts_en.append("“ESCO essentials”")

    sources_de = _join_sources(source_parts_de, "oder")
    sources_en = _join_sources(source_parts_en, "or")

    st.caption(
        tr(
            f"Ziehe Skills aus {sources_de} in „Muss-Anforderungen“ oder „Nice-to-have“, um die finale Auswahl festzulegen.",
            f"Drag skills from {sources_en} into “Must-have requirements” or “Nice-to-have” to finalise your selection.",
            lang=lang_code,
        )
    )

    tooltip_map: dict[str, list[str]] = {}
    for identifier, info in meta.items():
        label_text = info["label"]
        if len(label_text) <= MAX_INLINE_VALUE_CHARS:
            continue
        tooltip_map.setdefault(identifier, []).append(label_text)

    if tooltip_map:
        # ``<\/`` ensures the JSON payload stays valid inside the ``<script>`` tag
        # and avoids ``SyntaxWarning: invalid escape sequence`` during parsing.
        tooltip_payload = json.dumps(tooltip_map, ensure_ascii=False).replace("</", "<\\/")
        # ``__TOOLTIP_DATA_PLACEHOLDER__`` is intentionally used as a template marker and
        # replaced below to inject the escaped JSON payload safely. [PLH_SWEEP_GENERIC]
        st.markdown(
            """
            <script>
            const tooltipMap = __TOOLTIP_DATA_PLACEHOLDER__;
            const doc = window.parent?.document || window.document;
            const applySortableTooltips = () => {
                const workingCopy = JSON.parse(JSON.stringify(tooltipMap));
                const nodes = doc.querySelectorAll('.sortable-item');
                nodes.forEach((node) => {
                    const marker = node.querySelector('[data-skill-id]');
                    const skillId = marker?.getAttribute('data-skill-id') || node.getAttribute('data-skill-id');
                    if (!skillId) {
                        node.removeAttribute('title');
                        return;
                    }
                    node.setAttribute('data-skill-id', skillId);
                    const source = marker?.getAttribute('data-source') || node.getAttribute('data-source');
                    if (source) {
                        node.setAttribute('data-source', source);
                    }
                    const sourceLabel = marker?.getAttribute('data-source-label') || node.getAttribute('data-source-label') || '';
                    if (sourceLabel) {
                        node.setAttribute('data-source-label', sourceLabel);
                        node.setAttribute('aria-label', `${node.textContent.trim()} – ${sourceLabel}`.trim());
                    }
                    const sourceShort = marker?.getAttribute('data-source-short') || node.getAttribute('data-source-short');
                    if (sourceShort) {
                        node.setAttribute('data-source-short', sourceShort);
                    }
                    const entries = workingCopy[skillId];
                    if (entries && entries.length) {
                        const fullLabel = entries.shift();
                        const tooltip = sourceLabel ? `${fullLabel} • ${sourceLabel}` : fullLabel;
                        node.setAttribute('title', tooltip);
                        return;
                    }
                    if (sourceLabel) {
                        node.setAttribute('title', sourceLabel);
                        return;
                    }
                    node.removeAttribute('title');
                });
            };
            window.requestAnimationFrame(() => {
                setTimeout(applySortableTooltips, 0);
                setTimeout(applySortableTooltips, 300);
            });
            </script>
            """.replace("__TOOLTIP_DATA_PLACEHOLDER__", tooltip_payload),
            unsafe_allow_html=True,
        )

    final_must_hard: list[str] = []
    final_must_soft: list[str] = []
    final_nice_hard: list[str] = []
    final_nice_soft: list[str] = []

    for item in board_state["target_must"]:
        bubble_meta = meta.get(item)
        if not bubble_meta:
            continue
        label = bubble_meta["label"]
        if bubble_meta["category"] == "soft":
            if label not in final_must_soft:
                final_must_soft.append(label)
        else:
            if label not in final_must_hard:
                final_must_hard.append(label)

    for item in board_state["target_nice"]:
        bubble_meta = meta.get(item)
        if not bubble_meta:
            continue
        label = bubble_meta["label"]
        if bubble_meta["category"] == "soft":
            if label not in final_nice_soft:
                final_nice_soft.append(label)
        else:
            if label not in final_nice_hard:
                final_nice_hard.append(label)

    requirements["hard_skills_required"] = unique_normalized(final_must_hard)
    requirements["soft_skills_required"] = unique_normalized(final_must_soft)
    requirements["hard_skills_optional"] = unique_normalized(final_nice_hard)
    requirements["soft_skills_optional"] = unique_normalized(final_nice_soft)

    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": unique_normalized(final_must_hard + final_must_soft),
        "nice": unique_normalized(final_nice_hard + final_nice_soft),
    }


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


@dataclass
class FieldSourceInfo:
    """Structured information about the provenance of a field value."""

    descriptor: str
    context: str | None
    snippet: str | None
    confidence: float | None
    is_inferred: bool
    url: str | None

    def descriptor_with_context(self) -> str:
        """Return the descriptor enriched with optional context."""

        if self.context:
            return f"{self.descriptor} ({self.context})"
        return self.descriptor

    def tooltip(self) -> str:
        """Return a localized tooltip describing the source."""

        parts: list[str] = [self.descriptor_with_context()]
        if self.snippet:
            parts.append(self.snippet)
        if self.confidence is not None:
            percent = round(float(self.confidence) * 100)
            parts.append(
                tr(
                    "Vertrauen: {percent}%",
                    "Confidence: {percent}%",
                ).format(percent=percent)
            )
        if self.is_inferred:
            parts.append(tr("Durch KI abgeleitet", "Inferred by AI"))
        return " – ".join(part for part in parts if part)


# Index of the first data entry step ("Unternehmen" / "Company"). The value
# now lives in ``wizard.metadata`` so ``wizard_router`` and tests can rely on a
# single shared definition.

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


@dataclass(frozen=True)
class ComplianceToggleConfig:
    """Configuration describing a single compliance checkbox."""

    path: ProfilePaths
    label: LangPair
    help_text: LangPair


COMPLIANCE_TOGGLE_CONFIGS: Final[tuple[ComplianceToggleConfig, ...]] = (
    ComplianceToggleConfig(
        path=ProfilePaths.REQUIREMENTS_BACKGROUND_CHECK_REQUIRED,
        label=("Hintergrundprüfung verpflichtend", "Background check required"),
        help_text=(
            "Umfasst Identitäts-, Strafregister- und Beschäftigungshistorie-Prüfungen.",
            "Covers identity, criminal-record, and employment-history verification.",
        ),
    ),
    ComplianceToggleConfig(
        path=ProfilePaths.REQUIREMENTS_REFERENCE_CHECK_REQUIRED,
        label=("Referenzprüfung verpflichtend", "Reference check required"),
        help_text=(
            "Bestätigt frühere Vorgesetzte oder Kolleg:innen und deren Feedback.",
            "Confirms prior managers or peers and captures their feedback.",
        ),
    ),
    ComplianceToggleConfig(
        path=ProfilePaths.REQUIREMENTS_PORTFOLIO_REQUIRED,
        label=("Portfolio/Arbeitsproben verpflichtend", "Portfolio / work samples required"),
        help_text=(
            "Fordert aktuelle Arbeitsproben oder Case-Studys an.",
            "Requests up-to-date work samples or case studies.",
        ),
    ),
)


def _render_compliance_toggle_group(requirements: dict[str, Any]) -> None:
    """Render the compliance toggle set inside the active container."""

    if not isinstance(requirements, dict):
        return
    for config in COMPLIANCE_TOGGLE_CONFIGS:
        _render_compliance_toggle(requirements, config)


def _render_compliance_toggle(
    requirements: dict[str, Any],
    config: ComplianceToggleConfig,
) -> None:
    """Render a single checkbox and persist the linked profile state."""

    requirement_key = config.path.value.split(".")[-1]
    session_key = str(config.path)
    current_value = bool(requirements.get(requirement_key))

    def _sync_toggle() -> None:
        _update_profile(
            config.path,
            bool(st.session_state.get(session_key)),
        )

    checked = st.checkbox(
        tr(*config.label),
        value=current_value,
        key=session_key,
        on_change=_sync_toggle,
        help=tr(*config.help_text),
    )
    normalized = bool(checked)
    requirements[requirement_key] = normalized
    _update_profile(config.path, normalized)


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
    "company.contact_email": {
        "prompt": (
            "Welche E-Mail-Adresse sollen Kandidat:innen zur Kontaktaufnahme nutzen?",
            "Which email address should candidates use to reach you?",
        ),
        "description": (
            "Diese Adresse landet in Exporten und Follow-ups – bitte ein Postfach mit aktivem Monitoring angeben.",
            "This address is used in exports and follow-ups – please provide a monitored inbox.",
        ),
        "suggestions": (
            ["talent@firma.de", "jobs@unternehmen.com"],
            ["talent@company.com", "jobs@org.io"],
        ),
        "style": "warning",
    },
    "location.primary_city": {
        "prompt": (
            "In welcher Stadt arbeitet das Team überwiegend?",
            "Which city is the team primarily based in?",
        ),
        "description": (
            "Die Stadt hilft bei Gehaltsbandbreiten, Steuerungen für Zeitzonen und Office-Vorschlägen.",
            "Knowing the city informs salary bands, time zone handling, and office suggestions.",
        ),
        "suggestions": (
            ["Berlin", "München", "Remote (Berlin bevorzugt)"],
            ["Berlin", "Munich", "Remote (Berlin preferred)"],
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

    location_combined = ", ".join(part for part in (primary_city, country) if part)

    context: dict[str, str] = {
        "job_title": job_title,
        "company_name": company_name,
        "primary_city": primary_city,
        "country": country,
        "location_combined": location_combined,
    }

    return context


def _selected_intro_variant(variants: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    """Return the intro variant matching the configured tone."""

    if not variants:
        return None

    tone_value = st.session_state.get("wizard_intro_tone")
    tone = DEFAULT_INTRO_TONE
    if isinstance(tone_value, str):
        candidate = tone_value.strip().lower()
        if candidate in INTRO_TONES:
            tone = candidate

    try:
        tone_index = INTRO_TONES.index(tone)
    except ValueError:  # pragma: no cover - defensive fallback
        tone_index = 0

    safe_index = min(tone_index, len(variants) - 1)
    return variants[safe_index]


def _resolve_step_copy(
    page_key: str,
    profile: Mapping[str, Any] | None = None,
    *,
    context: Mapping[str, str] | None = None,
) -> tuple[str, str, list[str]]:
    """Resolve the localized header, subheader, and intro copy for a step."""

    page = PAGE_LOOKUP.get(page_key)
    if page is None:
        return "", "", []

    lang = st.session_state.get("lang", "de")
    title = page.header_for(lang)
    subtitle = page.subheader_for(lang)

    intro_context: Mapping[str, str]
    if context is not None:
        intro_context = context
    elif isinstance(profile, Mapping):
        intro_context = _build_profile_context(profile)
    else:
        intro_context = {}

    intros: list[str] = []
    variant = _selected_intro_variant(page.panel_intro_variants)
    if variant:
        template = page.translate(variant, lang)
        try:
            formatted = template.format(**intro_context)
        except Exception:
            formatted = template
        cleaned = formatted.strip()
        if cleaned:
            intros.append(cleaned)

    return title, subtitle, intros


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
    """Configuration for an automatically analysed company section."""

    key: str
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


def _get_company_info_cache() -> dict[str, Mapping[str, Any]]:
    """Return the mutable cache storing structured company lookups."""

    cache = st.session_state.get(StateKeys.COMPANY_INFO_CACHE)
    if isinstance(cache, dict):
        return cache
    cache = {}
    st.session_state[StateKeys.COMPANY_INFO_CACHE] = cache
    return cache


def _cache_brand_assets_from_html(url: str, raw_html: str | None) -> None:
    """Extract and cache branding assets from the provided HTML snippet."""

    if not raw_html or not raw_html.strip():
        return
    try:
        assets = extract_brand_assets(raw_html, base_url=url)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Brand asset extraction failed for %s: %s", url, exc)
        return
    if not any((assets.logo_url, assets.brand_color, assets.claim)):
        return
    cache = _get_company_info_cache()
    cache["branding"] = asdict(assets)


def _get_cached_brand_assets() -> Mapping[str, Any]:
    cache = _get_company_info_cache()
    branding = cache.get("branding")
    if isinstance(branding, Mapping):
        return branding
    return {}


def _coerce_brand_string(value: Any) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _coerce_brand_color(value: Any) -> str | None:
    candidate = _coerce_brand_string(value)
    if not candidate:
        return None
    upper = candidate.upper()
    if re.fullmatch(r"#?[0-9A-F]{6}", upper):
        return upper if upper.startswith("#") else f"#{upper}"
    return candidate


def _apply_branding_to_profile(profile: NeedAnalysisProfile) -> None:
    branding = _get_cached_brand_assets()
    if not branding:
        return

    logo_url = _coerce_brand_string(branding.get("logo_url"))
    if logo_url and not profile.company.logo_url:
        profile.company.logo_url = logo_url

    brand_color = _coerce_brand_color(branding.get("brand_color"))
    if brand_color and not profile.company.brand_color:
        profile.company.brand_color = brand_color

    claim = _coerce_brand_string(branding.get("claim"))
    if claim and not profile.company.claim:
        profile.company.claim = claim


def _remember_company_page_text(cache_key: str, text: str) -> None:
    """Persist ``text`` for ``cache_key`` in the in-memory session cache."""

    _get_company_page_text_cache()[cache_key] = text


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_esco_search(query: str, *, lang: str, limit: int) -> list[dict[str, str]]:
    """Return ESCO occupation matches with shared caching."""

    if not str(query or "").strip():
        return []
    return search_occupations(query, lang=lang, limit=limit)


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_esco_skills(occupation_uri: str, *, lang: str) -> list[str]:
    """Return ESCO essential skills with shared caching."""

    if not str(occupation_uri or "").strip():
        return []
    return get_essential_skills(occupation_uri, lang=lang)


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


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_extract_profile(
    text: str,
    *,
    title_hint: str | None,
    company_hint: str | None,
    url_hint: str | None,
    locked_items: tuple[tuple[str, str], ...],
    reasoning_effort: str,
) -> str:
    """Return cached structured extraction output for ``text``."""

    locked_fields = {key: value for key, value in locked_items}
    previous_effort: str | None
    try:
        previous_effort = st.session_state.get("reasoning_effort")
    except Exception:  # pragma: no cover - Streamlit session not initialised
        previous_effort = None

    try:
        if reasoning_effort and previous_effort != reasoning_effort:
            st.session_state["reasoning_effort"] = reasoning_effort
        return extract_json(
            text,
            title=title_hint,
            company=company_hint,
            url=url_hint,
            locked_fields=locked_fields or None,
        )
    finally:
        if reasoning_effort and previous_effort != reasoning_effort:
            st.session_state["reasoning_effort"] = previous_effort


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

    storage: dict[str, dict[str, str]] = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]
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
    normalized = extract_company_size(text)
    if normalized:
        return normalized
    snippet = extract_company_size_snippet(text)
    if snippet:
        return snippet.strip(" .,;") or None
    return None


def _record_company_enrichment_entry(
    metadata: dict[str, Any],
    *,
    field: str,
    value: str,
    rule: str,
    source_kind: str,
    source_label: str | None = None,
    source_section: str | None = None,
    source_url: str | None = None,
) -> None:
    """Update ``metadata`` with provenance for a company field."""

    rules_raw = metadata.get("rules")
    if isinstance(rules_raw, Mapping):
        rules = dict(rules_raw)
    else:
        rules = {}
    entry = dict(rules.get(field) or {})
    entry.update(
        {
            "rule": rule,
            "value": value,
            "source_kind": source_kind,
            "inferred": True,
        }
    )
    snippet = _truncate_snippet(value)
    if snippet:
        entry["source_text"] = snippet
    if source_section:
        entry["source_section"] = source_section
    if source_label:
        entry["source_section_label"] = source_label
    if source_url:
        entry["source_url"] = source_url
    rules[field] = entry
    metadata["rules"] = rules
    llm_fields_raw = metadata.get("llm_fields")
    llm_fields: set[str] = {field}
    if isinstance(llm_fields_raw, list):
        llm_fields.update({item for item in llm_fields_raw if isinstance(item, str)})
    metadata["llm_fields"] = sorted(llm_fields)


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
    _record_company_enrichment_entry(
        metadata,
        field=field,
        value=value,
        rule=f"company_page.{section_key}",
        source_kind="company_page",
        source_label=section_label,
        source_section=section_key,
        source_url=source_url,
    )
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
            "name": ("name", ProfilePaths.COMPANY_NAME),
            "location": ("hq_location", ProfilePaths.COMPANY_HQ_LOCATION),
            "mission": ("mission", ProfilePaths.COMPANY_MISSION),
            "culture": ("culture", ProfilePaths.COMPANY_CULTURE),
        }
        for source, (target, path) in mapping.items():
            if target not in company or not str(company.get(target, "")).strip():
                value = extracted.get(source)
                if isinstance(value, str) and value.strip():
                    normalized = value.strip()
                    _update_profile(path, normalized)
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
            _update_profile(ProfilePaths.COMPANY_SIZE, size_value)
            _record_company_page_source(
                "company.size",
                size_value,
                source_url=source_url,
                section_key="about",
                section_label=section_label,
            )


def _enrich_company_profile_via_web(
    profile: NeedAnalysisProfile,
    metadata: dict[str, Any],
    *,
    vector_store_id: str | None = None,
) -> None:
    """Populate missing company fields via web enrichment."""

    company = getattr(profile, "company", None)
    if company is None:
        return

    name_candidates = [
        str(company.name or "").strip(),
        str(company.brand_name or "").strip(),
    ]
    company_name = next((candidate for candidate in name_candidates if candidate), "")
    if not company_name:
        return

    missing_attrs: set[str] = set()
    for attr in ("name", "hq_location", "mission", "culture", "size"):
        current_value = getattr(company, attr, None)
        if isinstance(current_value, str):
            if current_value.strip():
                continue
        elif current_value is not None:
            continue
        missing_attrs.add(attr)

    if not missing_attrs:
        return

    cache = _get_company_info_cache()
    cache_key = company_name.casefold()
    cached = cache.get(cache_key)
    if cached is None:
        context_parts = [company_name]
        website_hint = str(getattr(company, "website", "") or "").strip()
        if website_hint:
            context_parts.append(f"Website: {website_hint}")
        query_text = "\n".join(part for part in context_parts if part)
        try:
            fetched = extract_company_info(query_text, vector_store_id=vector_store_id)
        except Exception:
            fetched = {}
        cache[cache_key] = dict(fetched) if isinstance(fetched, Mapping) else {}
        cached = cache[cache_key]

    if not isinstance(cached, Mapping) or not cached:
        return

    lang = getattr(st.session_state, "lang", None)
    source_label = tr("Websuche", "Web search", lang=lang)
    field_map = {
        "name": ("name", ProfilePaths.COMPANY_NAME),
        "location": ("hq_location", ProfilePaths.COMPANY_HQ_LOCATION),
        "mission": ("mission", ProfilePaths.COMPANY_MISSION),
        "culture": ("culture", ProfilePaths.COMPANY_CULTURE),
        "size": ("size", ProfilePaths.COMPANY_SIZE),
    }
    for source, (attr, path) in field_map.items():
        if attr not in missing_attrs:
            continue
        raw_value = cached.get(source)
        if not isinstance(raw_value, str):
            continue
        normalized = raw_value.strip()
        if not normalized:
            continue
        setattr(company, attr, normalized)
        _update_profile(path, normalized)
        _record_company_enrichment_entry(
            metadata,
            field=f"company.{attr}",
            value=normalized,
            rule="company_web.auto_enrich",
            source_kind="web_search",
            source_label=source_label,
            source_section="web_search",
        )


def _store_company_page_section(
    *,
    section: _CompanySectionConfig,
    url: str,
    text: str,
    lang: str,
) -> None:
    """Persist a fetched section and trigger enrichment where applicable."""

    try:
        text_hash = _hash_text(text)
        summary = _cached_summarize_company_page(url, text_hash, section["label"], lang)
    except Exception:
        summary = textwrap.shorten(text, width=420, placeholder="…")
        st.warning(
            tr(
                "KI-Zusammenfassung fehlgeschlagen – gekürzter Auszug angezeigt.",
                "AI summary failed – showing a shortened excerpt instead.",
            )
        )
    summaries: dict[str, dict[str, str]] = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]
    summaries[section["key"]] = {
        "url": url,
        "summary": summary,
        "label": section["label"],
    }
    if section["key"] == "about":
        _enrich_company_profile_from_about(
            text,
            source_url=url,
            section_label=section["label"],
        )


def _bulk_fetch_company_sections(
    base_url: str, sections: Sequence[_CompanySectionConfig]
) -> tuple[
    list[tuple[_CompanySectionConfig, str, str]],
    list[_CompanySectionConfig],
    list[tuple[_CompanySectionConfig, str]],
]:
    """Fetch multiple company sections concurrently."""

    successes: list[tuple[_CompanySectionConfig, str, str]] = []
    misses: list[_CompanySectionConfig] = []
    errors: list[tuple[_CompanySectionConfig, str]] = []
    if not sections:
        return successes, misses, errors

    max_workers = min(4, len(sections)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_section = {
            executor.submit(_fetch_company_page, base_url, section["slugs"]): section for section in sections
        }
        for future in as_completed(future_to_section):
            section = future_to_section[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - defensive safeguard
                errors.append((section, str(exc)))
                continue
            if not result:
                misses.append(section)
                continue
            url, text = result
            successes.append((section, url, text))
    return successes, misses, errors


def _load_company_page_section(
    section_key: str,
    base_url: str,
    slugs: Sequence[str],
    label: str,
) -> None:
    """Fetch and summarise a company section and store it in session state."""

    lang = st.session_state.get("lang", "de")
    with st.spinner(tr("Suche nach {section} …", "Fetching {section} …").format(section=label)):
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
    _store_company_page_section(
        section={"key": section_key, "label": label, "slugs": slugs},
        url=url,
        text=text,
        lang=lang,
    )
    st.success(tr("Zusammenfassung aktualisiert.", "Summary updated."))


def _render_company_research_tools(base_url: str) -> None:
    """Render buttons to analyse additional company web pages."""

    render_section_heading(
        tr("🔍 Automatische Recherche", "🔍 Automatic research"),
        description=tr(
            "Nutze den Button, um wichtige Unterseiten zu analysieren und kompakte Zusammenfassungen zu erhalten.",
            "Use the button to analyse key subpages and receive concise summaries.",
        ),
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
    st.caption(tr("Erkannte Website: {url}", "Detected website: {url}").format(url=f"[{display_url}]({display_url})"))

    sections: list[_CompanySectionConfig] = [
        {
            "key": "about",
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
            "label": tr("Presse", "Press"),
            "slugs": [
                "presse",
                "press",
                "newsroom",
                "news",
            ],
        },
    ]

    fetch_all_label = tr(
        "Informationen aus dem Web abrufen",
        "Get Info from Web",
    )
    if st.button(fetch_all_label, key="ui.company.page.fetch_all"):
        lang = st.session_state.get("lang", "de")
        summaries = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]
        pending_sections = [section for section in sections if not summaries.get(section["key"], {}).get("summary")]
        targets = pending_sections or sections
        with st.spinner(
            tr(
                "Analysiere verfügbare Unterseiten …",
                "Analysing available subpages …",
            )
        ):
            successes, misses, errors = _bulk_fetch_company_sections(normalised, targets)
            for section, url, text in successes:
                _store_company_page_section(
                    section=section,
                    url=url,
                    text=text,
                    lang=lang,
                )
        if successes:
            st.success(
                tr(
                    "{count} Seiten automatisch aktualisiert.",
                    "Automatically updated {count} sections.",
                ).format(count=len(successes))
            )
        if misses:
            st.info(
                tr(
                    "Keine passenden Seiten gefunden für: {labels}.",
                    "No matching pages found for: {labels}.",
                ).format(labels=", ".join(section["label"] for section in misses))
            )
        if errors:
            st.warning(
                tr(
                    "{count} Seiten konnten nicht verarbeitet werden (siehe Logs).",
                    "Failed to process {count} sections (see logs).",
                ).format(count=len(errors))
            )
        if not (successes or misses or errors):
            st.info(
                tr(
                    "Keine neuen Seiten zur Analyse gefunden.",
                    "No new pages to analyse.",
                )
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
    candidate = min(current + 1, total_steps - 1)
    st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, None)
    st.session_state[StateKeys.STEP] = candidate


def prev_step() -> None:
    """Return to the previous wizard step."""

    _request_scroll_to_top()
    st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, None)
    st.session_state[StateKeys.STEP] = max(0, st.session_state.get(StateKeys.STEP, 0) - 1)


def _clear_source_error_state() -> None:
    """Remove any persisted source error indicators."""

    st.session_state.pop("source_error", None)
    st.session_state.pop("source_error_message", None)


def _record_source_error(message: LocalizedMessage, detail: str | None = None) -> None:
    """Display and persist the localized onboarding source error."""

    display_error(message, detail)
    st.session_state["source_error"] = True
    st.session_state["source_error_message"] = resolve_message(
        message,
        lang=st.session_state.get("lang"),
    )


def on_file_uploaded() -> None:
    """Handle file uploads and populate job posting text."""

    f = st.session_state.get(UIKeys.PROFILE_FILE_UPLOADER)
    if not f:
        return

    _clear_source_error_state()
    try:
        doc = clean_structured_document(extract_text_from_file(f))
        txt = doc.text
    except ValueError as e:
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        msg = str(e).lower()
        if "doc conversion" in msg and ".docx" in msg:
            _record_source_error(
                tr(
                    "Word-Dateien im alten .doc-Format müssen vor dem Upload in .docx konvertiert werden.",
                    "Legacy .doc files must be converted to .docx before upload.",
                ),
                str(e),
            )
        elif "unsupported file type" in msg:
            _record_source_error(
                tr(
                    "Dieser Dateityp wird nicht unterstützt. Bitte laden Sie eine PDF-, DOCX- oder Textdatei hoch.",
                    "Unsupported file type. Please upload a PDF, DOCX, or text file.",
                ),
                str(e),
            )
        elif "file too large" in msg:
            _record_source_error(
                tr(
                    "Datei ist zu groß. Maximale Größe: 20 MB.",
                    "File is too large. Maximum size: 20 MB.",
                ),
                str(e),
            )
        elif "invalid pdf" in msg:
            _record_source_error(
                tr(
                    "Ungültige oder beschädigte PDF-Datei.",
                    "Invalid or corrupted PDF file.",
                ),
                str(e),
            )
        elif "requires ocr support" in msg or "possibly scanned pdf" in msg:
            _record_source_error(
                tr(
                    "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
                    "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
                ),
                str(e),
            )
        elif "file could not be read" in msg:
            _record_source_error(
                tr(
                    "Datei konnte nicht verarbeitet werden. Bitte Format prüfen oder erneut versuchen.",
                    "Failed to extract data from the file. Please check the format and try again.",
                ),
                str(e),
            )
        else:
            _record_source_error(
                tr(
                    "Datei enthält keinen Text – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                    "File contains no text – you can also enter the information manually in the following steps.",
                ),
            )
        return
    except Exception as e:  # pragma: no cover - defensive
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        _record_source_error(
            tr(
                "Datei konnte nicht gelesen werden. Prüfen Sie, ob es sich um ein gescanntes PDF handelt und installieren Sie ggf. OCR-Abhängigkeiten.",
                "Failed to read file. If this is a scanned PDF, install OCR dependencies or check the file quality.",
            ),
            str(e),
        )
        return
    if not txt.strip():
        _record_source_error(
            tr(
                "Datei enthält keinen Text – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "File contains no text – you can also enter the information manually in the following steps.",
            ),
        )
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

    _clear_source_error_state()
    if not is_supported_url(url):
        _record_source_error(
            tr(
                "Ungültige URL – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "Invalid URL – you can also enter the information manually in the following steps.",
            )
        )
        return
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
    try:
        doc = clean_structured_document(extract_text_from_url(url))
        _cache_brand_assets_from_html(url, getattr(doc, "raw_html", None))
        txt = doc.text
    except Exception as e:  # pragma: no cover - defensive
        st.session_state.pop("__prefill_profile_doc__", None)
        st.session_state[StateKeys.RAW_BLOCKS] = []
        error_message = tr(
            "❌ URL konnte nicht geladen werden. Bitte Adresse prüfen.",
            "❌ URL could not be fetched. Please check the address.",
        )
        _record_source_error(error_message, str(e))
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = error_message
        return
    if not txt or not txt.strip():
        _record_source_error(
            tr(
                "Keine Textinhalte gefunden – Sie können die Informationen auch manuell in den folgenden Schritten eingeben.",
                "No text content found – you can also enter the information manually in the following steps.",
            ),
        )
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
    rule_patch: dict[str, Any] = {}
    if rule_matches:
        rule_patch = matches_to_patch(rule_matches)
        st.session_state[StateKeys.PROFILE] = rule_patch
        st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = rule_patch
        new_meta = build_rule_metadata(rule_matches)
        annotated_rules = _annotate_rule_metadata(new_meta.get("rules"), raw_blocks, doc)
        existing_rules = metadata.get("rules") or {}
        if not isinstance(existing_rules, Mapping):
            existing_rules = {}
        combined_rules = {**dict(existing_rules), **annotated_rules}
        locked = set(metadata.get("locked_fields", [])) | set(new_meta.get("locked_fields", []))
        high_conf = set(metadata.get("high_confidence_fields", [])) | set(new_meta.get("high_confidence_fields", []))
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

    llm_error: Exception | None = None
    extraction_warning: str | None = None
    extracted_data: dict[str, Any] = {}
    recovered = False
    locked_items = tuple(sorted(locked_hints.items()))
    effort_value = str(st.session_state.get("reasoning_effort", REASONING_EFFORT) or REASONING_EFFORT)
    try:
        raw_json = _cached_extract_profile(
            text,
            title_hint=title_hint,
            company_hint=company_hint,
            url_hint=url_hint,
            locked_items=locked_items,
            reasoning_effort=effort_value,
        )
    except ExtractionError as exc:
        llm_error = exc
    else:
        try:
            extracted_data, recovered = parse_structured_payload(raw_json)
        except InvalidExtractionPayload as exc:
            llm_error = exc

    if llm_error:
        extracted_data = deepcopy(rule_patch)
        errors_map = metadata.get("llm_errors")
        if isinstance(errors_map, Mapping):
            errors_map = dict(errors_map)
        else:
            errors_map = {}
        detail_text = str(llm_error).strip()
        errors_map["extraction"] = detail_text
        metadata["llm_errors"] = errors_map
        extraction_warning = tr(
            "⚠️ KI-Extraktion konnte nicht abgeschlossen werden – Felder bitte manuell prüfen.",
            "⚠️ AI extraction could not complete – please review the fields manually.",
        )
        warning_summary: dict[str, str] = {
            tr("Status", "Status"): extraction_warning,
        }
        if detail_text:
            warning_summary[tr("Fehlerdetails", "Error details")] = detail_text
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = warning_summary
        st.session_state[StateKeys.STEPPER_WARNING] = extraction_warning
    else:
        st.session_state.pop(StateKeys.STEPPER_WARNING, None)
        if not extracted_data:
            extracted_data = {}

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
    _apply_branding_to_profile(profile)
    profile = apply_basic_fallbacks(profile, text, metadata=metadata)
    _enrich_company_profile_via_web(profile, metadata, vector_store_id=vector_store_id or None)
    lang = getattr(st.session_state, "lang", "en") or "en"
    job_title_value = (profile.position.job_title or "").strip()
    occupation_options: list[dict[str, str]] = []
    selected_ids: list[str] = []
    if job_title_value:
        occupation_options = _sanitize_esco_options(search_occupations(job_title_value, lang=lang, limit=5))
        classified = classify_occupation(job_title_value, lang=lang)
        if classified:
            label = str(classified.get("preferredLabel") or "").strip()
            uri = str(classified.get("uri") or "").strip()
            group = str(classified.get("group") or "").strip()
            normalized_meta = dict(classified)
            if label:
                normalized_meta["preferredLabel"] = label
            if uri:
                normalized_meta["uri"] = uri
            if group:
                normalized_meta["group"] = group
            if uri and all(entry.get("uri") != uri for entry in occupation_options):
                occupation_options.insert(0, normalized_meta)
            elif not uri:
                occupation_options.insert(0, normalized_meta)

        previous_selected = st.session_state.get(StateKeys.ESCO_SELECTED_OCCUPATIONS, []) or []
        prev_ids = [
            str(entry.get("uri") or "").strip()
            for entry in previous_selected
            if isinstance(entry, Mapping) and str(entry.get("uri") or "").strip()
        ]
        option_map = {str(entry.get("uri") or "").strip(): entry for entry in occupation_options if entry.get("uri")}
        selected_ids = [uri for uri in prev_ids if uri in option_map]
        if not selected_ids:
            primary_uri = str(classified.get("uri") if isinstance(classified, Mapping) else "").strip()
            if primary_uri and primary_uri in option_map:
                selected_ids = [primary_uri]
        if not selected_ids and occupation_options:
            first_uri = str(occupation_options[0].get("uri") or "").strip()
            if first_uri:
                selected_ids = [first_uri]

        if occupation_options:
            st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = occupation_options
            selected_entries = [
                dict(entry) for entry in occupation_options if str(entry.get("uri") or "").strip() in set(selected_ids)
            ]
        if not selected_entries and occupation_options:
            selected_entries = [dict(occupation_options[0])]
            selected_ids = [str(occupation_options[0].get("uri") or "").strip()]
        st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = selected_entries
        st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = [sid for sid in selected_ids if sid]
        primary_meta = selected_entries[0] if selected_entries else None
        if primary_meta:
            label_raw = primary_meta.get("preferredLabel")
            uri_raw = primary_meta.get("uri")
            group_raw = primary_meta.get("group")
            selected_label: str | None = str(label_raw).strip() if label_raw else None
            selected_uri: str | None = str(uri_raw).strip() if uri_raw else None
            selected_group: str | None = str(group_raw).strip() if group_raw else None
            profile.position.occupation_label = selected_label or None
            profile.position.occupation_uri = selected_uri or None
            profile.position.occupation_group = selected_group or None
            _refresh_esco_skills(selected_entries, lang=lang)
        else:
            profile.position.occupation_label = None
            profile.position.occupation_uri = None
            profile.position.occupation_group = None
            st.session_state[StateKeys.ESCO_SKILLS] = []
    else:
        st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = []
        st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = []
        st.session_state[StateKeys.ESCO_SKILLS] = []
        st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = []
        profile.position.occupation_label = None
        profile.position.occupation_uri = None
        profile.position.occupation_group = None

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
    if recovered:
        mark_low_confidence(metadata, data)
    st.session_state[StateKeys.PROFILE] = data
    _prime_widget_state_from_profile(data)
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = data
    if extraction_warning is None:
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
        hard_total = len(profile.requirements.hard_skills_required) + len(profile.requirements.hard_skills_optional)
        if hard_total:
            summary[tr("Hard Skills", "Hard skills")] = str(hard_total)
        soft_total = len(profile.requirements.soft_skills_required) + len(profile.requirements.soft_skills_optional)
        if soft_total:
            summary[tr("Soft Skills", "Soft skills")] = str(soft_total)
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = summary
    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": unique_normalized(data.get("requirements", {}).get("hard_skills_required", [])),
        "nice": unique_normalized(data.get("requirements", {}).get("hard_skills_optional", [])),
    }
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
    st.session_state[StateKeys.EXTRACTION_MISSING] = missing
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
                done = set(st.session_state[StateKeys.PROFILE].get("meta", {}).get("followups_answered", []))
                st.session_state[StateKeys.FOLLOWUPS] = [
                    q for q in followup_res.get("questions", []) if q.get("field") not in done
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
    if doc and raw_input and raw_input.strip() and raw_input.strip() != doc.text.strip():
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
        with WIZARD_TRACER.start_as_current_span("llm.extract") as span:
            try:
                _extract_and_summarize(raw_clean, schema)
            except Exception as span_exc:
                span.record_exception(span_exc)
                span.set_status(Status(StatusCode.ERROR, span_exc.__class__.__name__))
                raise
    except Exception as exc:
        st.session_state.pop("__last_extracted_hash__", None)
        warning_message = tr(
            "⚠️ Extraktion fehlgeschlagen – bitte prüfen Sie die Felder manuell.",
            "⚠️ Extraction failed – please review the fields manually.",
        )
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = warning_message
        st.session_state[StateKeys.STEPPER_WARNING] = warning_message
        display_error(
            tr(
                "Automatische Extraktion fehlgeschlagen",
                "Automatic extraction failed",
            ),
            str(exc),
        )
    else:
        st.rerun()


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
    "company.name": ("Unternehmen", "Company"),
    "company.hq_location": ("Hauptsitz (Stadt, Land)", "Headquarters (city, country)"),
    "company.website": ("Website", "Website"),
    "company.contact_name": ("HR-Ansprechperson", "HR contact person"),
    "company.contact_email": ("Kontakt-E-Mail (Unternehmen)", "Company contact email"),
    "company.contact_phone": ("Kontakt-Telefon", "Contact phone"),
    "position.job_title": ("Jobtitel", "Job Title"),
    "position.role_summary": ("Rollenbeschreibung", "Role Summary"),
    "location.primary_city": ("Primärer Standort (Stadt)", "Primary location (city)"),
    "location.country": ("Land (Primärstandort)", "Country (primary location)"),
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


def _has_value(value: Any) -> bool:
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

    render_section_heading(
        tr(
            "Automatisch erkannte Informationen",
            "Automatically detected information",
        ),
        description=tr(
            "Alle Felder lassen sich später weiterhin bearbeiten.",
            "You can still adjust every field later on.",
        ),
    )

    if layout == "grid":
        cards: list[tuple[str, Any]] = [(path, value) for _, entries in section_entries for path, value in entries]
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
                st.markdown("<div style='margin-bottom:0.6rem'></div>", unsafe_allow_html=True)


def _ensure_extraction_review_styles() -> None:
    """Inject shared styles for the extraction review cards once per session."""

    if st.session_state.get(EXTRACTION_REVIEW_STYLE_KEY):
        return
    st.session_state[EXTRACTION_REVIEW_STYLE_KEY] = True
    st.markdown(
        """
        <style>
            .extraction-review-card {
                background: var(--surface-0, rgba(241, 245, 249, 0.65));
                border-radius: 18px;
                padding: 1.1rem 1.25rem;
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
                margin-bottom: 1.1rem;
            }

            .extraction-review-card h5 {
                margin: 0 0 0.75rem 0;
                font-size: 1.02rem;
                font-weight: 640;
            }

            .extraction-review-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: clamp(0.75rem, 2vw, 1.25rem);
            }

            .wizard-followup-card {
                background: var(--surface-0, rgba(226, 232, 240, 0.65));
                border-radius: 20px;
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.4));
                padding: 1.25rem 1.35rem;
                margin-top: 1rem;
                box-shadow: 0 12px 26px rgba(15, 23, 42, 0.16);
                animation: wizardFollowupCardIn 0.4s var(--transition-base, 0.18s ease-out) 1;
            }

            .wizard-followup-item {
                border-radius: 16px;
                padding: 0.85rem 1rem;
                background: var(--surface-1, rgba(255, 255, 255, 0.85));
                margin-bottom: 0.65rem;
                border: 1px solid transparent;
                opacity: 0;
                transform: translateY(6px);
                animation: wizardFollowupRowIn 0.35s ease-out forwards;
                transition:
                    border-color var(--transition-base, 0.18s ease-out),
                    box-shadow var(--transition-base, 0.18s ease-out),
                    transform var(--transition-base, 0.18s ease-out);
                will-change: transform, box-shadow;
            }

            .wizard-followup-item:focus-within,
            .wizard-followup-item:hover {
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
                transform: translateY(-1px);
            }

            .wizard-followup-item.fu-highlight {
                border-color: rgba(220, 38, 38, 0.55);
                box-shadow: 0 0 0 2px rgba(248, 113, 113, 0.35);
            }

            .wizard-followup-item.fu-highlight-soft {
                border-color: rgba(59, 130, 246, 0.35);
                box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.25);
            }

            .wizard-followup-question {
                font-weight: 620;
                margin-bottom: 0.45rem;
                color: var(--text-strong, #0f172a);
            }

            .wizard-followup-question.is-critical::before {
                content: "*";
                color: #dc2626;
                margin-right: 0.35rem;
            }

            .wizard-followup-chip {
                display: inline-flex;
                margin-right: 0.45rem;
            }

            .wizard-followup-chip button {
                border-radius: 999px;
                border: 1px solid rgba(148, 163, 184, 0.45);
                background: rgba(191, 219, 254, 0.55);
                padding: 0.2rem 0.85rem;
                font-size: 0.85rem;
                color: var(--text-strong, #0f172a);
                transition:
                    transform var(--transition-base, 0.18s ease-out),
                    box-shadow var(--transition-base, 0.18s ease-out),
                    background-color var(--transition-base, 0.18s ease-out);
            }

            .wizard-followup-chip button:hover {
                transform: translateY(-1px);
                box-shadow: 0 8px 16px rgba(37, 58, 95, 0.2);
            }

            .wizard-followup-chip button:focus-visible {
                outline: 2px solid rgba(37, 99, 235, 0.8);
                outline-offset: 2px;
            }

            @keyframes wizardFollowupCardIn {
                0% {
                    opacity: 0;
                    transform: translateY(8px);
                }
                100% {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes wizardFollowupRowIn {
                0% {
                    opacity: 0;
                    transform: translateY(12px);
                }
                100% {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @media (max-width: 960px) {
                .extraction-review-card {
                    padding: 1rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_followup_styles() -> None:
    """Ensure follow-up specific styles are injected once."""

    if st.session_state.get(FOLLOWUP_STYLE_KEY):
        return
    st.session_state[FOLLOWUP_STYLE_KEY] = True
    st.markdown(
        """
        <style>
            .wizard-followup-card > p:first-child {
                font-size: 0.98rem;
                font-weight: 560;
                margin-bottom: 0.6rem;
            }

            .wizard-followup-meta {
                font-size: 0.82rem;
                color: var(--text-faint, rgba(100, 116, 139, 0.95));
                margin-bottom: 0.65rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_followup_suggestion(field: str, key: str, suggestion: str) -> None:
    """Persist ``suggestion`` into the widget state for ``field``."""

    normalized = suggestion.strip()
    if not normalized:
        return
    if field in YES_NO_FOLLOWUP_FIELDS:
        lowered = normalized.casefold()
        st.session_state[key] = lowered in {"yes", "ja", "true", "wahr", "1", "y"}
        st.session_state[f"{key}_touched"] = True
        return
    if field in DATE_FOLLOWUP_FIELDS:
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError:
            parsed = None
        if parsed is not None:
            st.session_state[key] = parsed
        else:
            st.session_state[key] = normalized
        return
    if field in NUMBER_FOLLOWUP_FIELDS:
        cleaned = normalized.replace(",", ".")
        try:
            st.session_state[key] = int(float(cleaned))
        except ValueError:
            st.session_state[key] = normalized
        return
    if field in LIST_FOLLOWUP_FIELDS:
        current = str(st.session_state.get(key, "") or "")
        items = [line.strip() for line in current.splitlines() if line.strip()]
        if normalized not in items:
            items.append(normalized)
        st.session_state[key] = "\n".join(items)
        return
    st.session_state[key] = normalized


def _coerce_followup_number(value: Any) -> int:
    """Convert ``value`` into an ``int`` for numeric follow-up widgets."""

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return 0
        try:
            return int(float(cleaned.replace(",", ".")))
        except ValueError:
            return 0
    return 0


def _render_extraction_review() -> None:
    """Render tabbed overview of extracted profile data."""

    profile = _get_profile_state()
    flattened = flatten(profile)
    if not any(_has_value(value) for value in flattened.values()):
        st.info(
            tr(
                "Noch keine strukturierten Daten verfügbar – lade eine Stellenanzeige hoch oder füge Text ein.",
                "No structured data yet – upload a job ad or paste text to begin.",
            )
        )
        return

    _ensure_extraction_review_styles()
    render_section_heading(
        tr("Extraktion prüfen & anpassen", "Review and adjust extracted data"),
        description=tr(
            "Alle Felder lassen sich hier schnell überarbeiten, bevor du tiefer in die einzelnen Schritte gehst.",
            "Fine-tune every extracted field here before diving into the detailed steps.",
        ),
    )

    tabs = st.tabs(
        [
            tr("Unternehmen", "Company"),
            tr("Team & Kontext", "Team & context"),
            tr("Standort & Rahmen", "Location & logistics"),
            tr("Anforderungen", "Requirements"),
            tr("Prozess", "Process"),
        ]
    )

    with tabs[0]:
        _render_review_company_tab(profile)
    with tabs[1]:
        _render_review_role_tab(profile)
    with tabs[2]:
        _render_review_logistics_tab(profile)
    with tabs[3]:
        _render_review_requirements_tab(profile)
    with tabs[4]:
        _render_review_process_tab(profile)


def _render_review_company_tab(profile: dict[str, Any]) -> None:
    """Render company and branding fields within the extraction review."""

    company = profile.setdefault("company", {})
    location = profile.setdefault("location", {})

    st.markdown("<div class='extraction-review-card'>", unsafe_allow_html=True)
    st.markdown(f"<h5>{html.escape(tr('Unternehmensprofil', 'Company profile'))}</h5>", unsafe_allow_html=True)

    info_cols = st.columns((1.2, 1.2), gap="medium")
    company["name"] = widget_factory.text_input(
        ProfilePaths.COMPANY_NAME,
        tr(*COMPANY_NAME_LABEL),
        widget_factory=info_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    company["brand_name"] = widget_factory.text_input(
        ProfilePaths.COMPANY_BRAND_NAME,
        tr("Marke/Tochter", "Brand/Subsidiary"),
        widget_factory=info_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    detail_cols = st.columns((1.2, 1.2), gap="medium")
    company["industry"] = widget_factory.text_input(
        ProfilePaths.COMPANY_INDUSTRY,
        tr("Branche", "Industry"),
        widget_factory=detail_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    company["website"] = widget_factory.text_input(
        ProfilePaths.COMPANY_WEBSITE,
        tr("Website", "Website"),
        widget_factory=detail_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    contact_cols = st.columns(3, gap="small")
    company["contact_name"] = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_NAME,
        tr(*COMPANY_CONTACT_NAME_LABEL),
        widget_factory=contact_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    company["contact_email"] = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        tr(*COMPANY_CONTACT_EMAIL_LABEL),
        widget_factory=contact_cols[1].text_input,
        value_formatter=_string_or_empty,
    )
    company["contact_phone"] = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_PHONE,
        tr(*COMPANY_CONTACT_PHONE_LABEL),
        widget_factory=contact_cols[2].text_input,
        value_formatter=_string_or_empty,
    )

    location_cols = st.columns((1.2, 1.2), gap="medium")
    location["primary_city"] = widget_factory.text_input(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        tr(*PRIMARY_CITY_LABEL),
        widget_factory=location_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    location["country"] = widget_factory.text_input(
        ProfilePaths.LOCATION_COUNTRY,
        tr(*PRIMARY_COUNTRY_LABEL),
        widget_factory=location_cols[1].text_input,
        value_formatter=_string_or_empty,
    )
    company["hq_location"] = widget_factory.text_input(
        ProfilePaths.COMPANY_HQ_LOCATION,
        tr("Hauptsitz", "Headquarters"),
        value_formatter=_string_or_empty,
    )

    brand_cols = st.columns((1.2, 1.2), gap="medium")
    company["claim"] = widget_factory.text_input(
        ProfilePaths.COMPANY_CLAIM,
        tr("Claim/Slogan", "Claim/Tagline"),
        widget_factory=brand_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    company["brand_color"] = widget_factory.text_input(
        ProfilePaths.COMPANY_BRAND_COLOR,
        tr("Markenfarbe (Hex)", "Brand colour (hex)"),
        widget_factory=brand_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    company["brand_keywords"] = widget_factory.text_input(
        ProfilePaths.COMPANY_BRAND_KEYWORDS,
        tr("Markenbegriffe", "Brand keywords"),
        value_formatter=_string_or_empty,
    )

    company["logo_url"] = widget_factory.text_input(
        ProfilePaths.COMPANY_LOGO_URL,
        tr("Logo-URL", "Logo URL"),
        value_formatter=_string_or_empty,
    )

    upload_col, preview_col = st.columns((1.4, 1), gap="medium")
    with upload_col:
        logo_upload = st.file_uploader(
            tr("Logo hochladen", "Upload logo"),
            type=["png", "jpg", "jpeg", "svg"],
            key=UIKeys.COMPANY_LOGO,
            help=tr(
                "Erkannte Farbinformationen füllen automatisch das Markenfarbfeld.",
                "Detected colours will automatically pre-fill the brand colour field.",
            ),
        )
        if logo_upload is not None:
            _set_company_logo(logo_upload.getvalue())
    with preview_col:
        logo_bytes = _get_company_logo_bytes()
        if logo_bytes:
            st.image(logo_bytes, caption=tr("Aktuelles Logo", "Current logo"), use_column_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_review_role_tab(profile: dict[str, Any]) -> None:
    """Render role and team fields within the extraction review."""

    position = profile.setdefault("position", {})
    department = profile.setdefault("department", {})
    team = profile.setdefault("team", {})
    meta = profile.setdefault("meta", {})

    st.markdown("<div class='extraction-review-card'>", unsafe_allow_html=True)
    st.markdown(f"<h5>{html.escape(tr('Rollenübersicht', 'Role overview'))}</h5>", unsafe_allow_html=True)

    title_cols = st.columns((1.2, 1.2), gap="medium")
    position["job_title"] = widget_factory.text_input(
        ProfilePaths.POSITION_JOB_TITLE,
        tr("Jobtitel", "Job title"),
        widget_factory=title_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    department["name"] = widget_factory.text_input(
        ProfilePaths.DEPARTMENT_NAME,
        tr("Abteilung", "Department"),
        widget_factory=title_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    reporting_cols = st.columns((1.2, 1.2), gap="medium")
    team_reporting_value = widget_factory.text_input(
        ProfilePaths.TEAM_REPORTING_LINE,
        tr("Berichtslinie", "Reporting line"),
        widget_factory=reporting_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    team["reporting_line"] = team_reporting_value
    position["reporting_line"] = team_reporting_value
    position["reporting_manager_name"] = widget_factory.text_input(
        ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
        tr("Vorgesetzte Person", "Reporting manager"),
        widget_factory=reporting_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    dept_cols = st.columns((1.2, 1.2), gap="medium")
    department["function"] = widget_factory.text_input(
        ProfilePaths.DEPARTMENT_FUNCTION,
        tr("Funktion", "Function"),
        widget_factory=dept_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    department["leader_name"] = widget_factory.text_input(
        ProfilePaths.DEPARTMENT_LEADER_NAME,
        tr("Abteilungsleitung", "Department lead"),
        widget_factory=dept_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    team_cols = st.columns((1.2, 1.2), gap="medium")
    team["name"] = widget_factory.text_input(
        ProfilePaths.TEAM_NAME,
        tr("Teamname", "Team name"),
        widget_factory=team_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    team["mission"] = widget_factory.text_input(
        ProfilePaths.TEAM_MISSION,
        tr("Teamauftrag", "Team mission"),
        widget_factory=team_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    position["role_summary"] = st.text_area(
        tr(*ROLE_SUMMARY_LABEL),
        value=position.get("role_summary", ""),
        key=ProfilePaths.POSITION_ROLE_SUMMARY,
        height=130,
    )

    key_projects = st.text_area(
        tr("Schlüsselprojekte", "Key projects"),
        value=position.get("key_projects", ""),
        key=ProfilePaths.POSITION_KEY_PROJECTS,
        height=110,
    )
    position["key_projects"] = key_projects
    _update_profile(ProfilePaths.POSITION_KEY_PROJECTS, key_projects)

    metrics_cols = st.columns((1.2, 1.2), gap="medium")
    team_size_default = _coerce_followup_number(position.get("team_size"))
    team_size_value = metrics_cols[0].number_input(
        tr("Teamgröße", "Team size"),
        min_value=0,
        value=team_size_default,
        step=1,
        key=str(ProfilePaths.POSITION_TEAM_SIZE),
    )
    position["team_size"] = int(team_size_value)
    _update_profile(ProfilePaths.POSITION_TEAM_SIZE, int(team_size_value))

    supervises_default = _coerce_followup_number(position.get("supervises"))
    supervises_value = metrics_cols[1].number_input(
        tr("Direkte Reports", "Direct reports"),
        min_value=0,
        value=supervises_default,
        step=1,
        key=str(ProfilePaths.POSITION_SUPERVISES),
    )
    position["supervises"] = int(supervises_value)
    _update_profile(ProfilePaths.POSITION_SUPERVISES, int(supervises_value))

    schedule_cols = st.columns((1.2, 1.2), gap="medium")
    target_start = schedule_cols[0].date_input(
        tr("Gewünschtes Startdatum", "Desired start date"),
        value=_default_date(meta.get("target_start_date")),
        format="YYYY-MM-DD",
        key=str(ProfilePaths.META_TARGET_START_DATE),
    )
    target_start_iso = target_start.isoformat() if isinstance(target_start, date) else ""
    meta["target_start_date"] = target_start_iso
    _update_profile(
        ProfilePaths.META_TARGET_START_DATE,
        target_start_iso,
        session_value=target_start,
    )

    application_deadline = schedule_cols[1].date_input(
        tr("Bewerbungsschluss", "Application deadline"),
        value=_default_date(meta.get("application_deadline")),
        format="YYYY-MM-DD",
        key=str(ProfilePaths.META_APPLICATION_DEADLINE),
    )
    application_deadline_iso = application_deadline.isoformat() if isinstance(application_deadline, date) else ""
    meta["application_deadline"] = application_deadline_iso
    _update_profile(
        ProfilePaths.META_APPLICATION_DEADLINE,
        application_deadline_iso,
        session_value=application_deadline,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_review_logistics_tab(profile: dict[str, Any]) -> None:
    """Render location and employment logistics for the extraction review."""

    location = profile.setdefault("location", {})
    employment = profile.setdefault("employment", {})

    st.markdown("<div class='extraction-review-card'>", unsafe_allow_html=True)
    st.markdown(
        f"<h5>{html.escape(tr('Standort & Rahmenbedingungen', 'Location & logistics'))}</h5>", unsafe_allow_html=True
    )

    loc_cols = st.columns((1.2, 1.2), gap="medium")
    location["onsite_ratio"] = widget_factory.text_input(
        ProfilePaths.LOCATION_ONSITE_RATIO,
        tr("Vor-Ort-Anteil", "Onsite ratio"),
        widget_factory=loc_cols[0].text_input,
        value_formatter=_string_or_empty,
    )
    employment["work_policy"] = widget_factory.text_input(
        ProfilePaths.EMPLOYMENT_WORK_POLICY,
        tr("Arbeitsmodell", "Work policy"),
        widget_factory=loc_cols[1].text_input,
        value_formatter=_string_or_empty,
    )

    remote_default = _coerce_followup_number(employment.get("remote_percentage"))
    remote_value = st.slider(
        tr("Remote-Anteil", "Remote percentage"),
        min_value=0,
        max_value=100,
        step=5,
        value=remote_default,
        key=str(ProfilePaths.EMPLOYMENT_REMOTE_PERCENTAGE),
    )
    employment["remote_percentage"] = int(remote_value)
    _update_profile(ProfilePaths.EMPLOYMENT_REMOTE_PERCENTAGE, int(remote_value))

    toggle_cols = st.columns(3, gap="medium")
    travel_required = toggle_cols[0].checkbox(
        tr("Reisetätigkeit?", "Travel required?"),
        value=bool(employment.get("travel_required")),
        key=str(ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED),
        help=tr(*EMPLOYMENT_TRAVEL_TOGGLE_HELP),
    )
    employment["travel_required"] = bool(travel_required)
    _update_profile(ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED, bool(travel_required))

    relocation_support = toggle_cols[1].checkbox(
        tr("Relocation möglich?", "Relocation support?"),
        value=bool(employment.get("relocation_support")),
        key=str(ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT),
        help=tr(*EMPLOYMENT_RELOCATION_TOGGLE_HELP),
    )
    employment["relocation_support"] = bool(relocation_support)
    _update_profile(ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT, bool(relocation_support))

    visa_support = toggle_cols[2].checkbox(
        tr("Visa-Sponsoring?", "Visa sponsorship?"),
        value=bool(employment.get("visa_sponsorship")),
        key=str(ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP),
        help=tr(*EMPLOYMENT_VISA_TOGGLE_HELP),
    )
    employment["visa_sponsorship"] = bool(visa_support)
    _update_profile(ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP, bool(visa_support))

    if travel_required:
        st.markdown("---")
        travel_cols = st.columns((1, 1.4, 1.4), gap="medium")
        travel_share = travel_cols[0].slider(
            tr("Reiseanteil (%)", "Travel share (%)"),
            min_value=0,
            max_value=100,
            step=5,
            value=_coerce_followup_number(employment.get("travel_share")),
            key=str(ProfilePaths.EMPLOYMENT_TRAVEL_SHARE),
        )
        employment["travel_share"] = int(travel_share)
        _update_profile(ProfilePaths.EMPLOYMENT_TRAVEL_SHARE, int(travel_share))

        with travel_cols[1]:
            travel_regions = render_list_text_area(
                label=tr("Reisegebiete (eine pro Zeile)", "Travel regions (one per line)"),
                session_key=f"review.{ProfilePaths.EMPLOYMENT_TRAVEL_REGIONS}",
                items=_normalize_list(employment.get("travel_regions")),
                height=110,
            )
        employment["travel_regions"] = travel_regions
        _update_profile(ProfilePaths.EMPLOYMENT_TRAVEL_REGIONS, travel_regions)

        with travel_cols[2]:
            travel_details = st.text_input(
                tr("Reise-Details", "Travel details"),
                value=_string_or_empty(employment.get("travel_details")),
                key=str(ProfilePaths.EMPLOYMENT_TRAVEL_DETAILS),
            )
        employment["travel_details"] = travel_details
        _update_profile(ProfilePaths.EMPLOYMENT_TRAVEL_DETAILS, travel_details)

    if relocation_support:
        relocation_details = st.text_input(
            tr("Relocation-Details", "Relocation details"),
            value=_string_or_empty(employment.get("relocation_details")),
            key=str(ProfilePaths.EMPLOYMENT_RELOCATION_DETAILS),
        )
        employment["relocation_details"] = relocation_details
        _update_profile(ProfilePaths.EMPLOYMENT_RELOCATION_DETAILS, relocation_details)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_review_requirements_tab(profile: dict[str, Any]) -> None:
    """Render responsibility and requirement fields for review."""

    responsibilities = profile.setdefault("responsibilities", {})
    requirements = profile.setdefault("requirements", {})

    st.markdown("<div class='extraction-review-card'>", unsafe_allow_html=True)
    st.markdown(
        f"<h5>{html.escape(tr('Anforderungen & Aufgaben', 'Requirements & responsibilities'))}</h5>",
        unsafe_allow_html=True,
    )

    resp_items = render_list_text_area(
        label=tr("Aufgaben (eine pro Zeile)", "Responsibilities (one per line)"),
        session_key=str(ProfilePaths.RESPONSIBILITIES_ITEMS),
        items=responsibilities.get("items"),
        height=150,
    )
    responsibilities["items"] = resp_items
    _update_profile(ProfilePaths.RESPONSIBILITIES_ITEMS, resp_items)

    hard_required = render_list_text_area(
        label=tr("Pflicht-Hard-Skills", "Required hard skills"),
        session_key=str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
        items=requirements.get("hard_skills_required"),
        height=120,
    )
    requirements["hard_skills_required"] = hard_required
    _update_profile(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED, hard_required)

    soft_required = render_list_text_area(
        label=tr("Pflicht-Soft-Skills", "Required soft skills"),
        session_key=str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
        items=requirements.get("soft_skills_required"),
        height=120,
    )
    requirements["soft_skills_required"] = soft_required
    _update_profile(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED, soft_required)

    tools = render_list_text_area(
        label=tr("Tools & Technologien", "Tools & technologies"),
        session_key=str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
        items=requirements.get("tools_and_technologies"),
        height=120,
    )
    requirements["tools_and_technologies"] = tools
    _update_profile(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES, tools)

    languages = render_list_text_area(
        label=tr("Sprachen", "Languages"),
        session_key=str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED),
        items=requirements.get("languages_required"),
        height=110,
    )
    requirements["languages_required"] = languages
    _update_profile(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED, languages)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_review_process_tab(profile: dict[str, Any]) -> None:
    """Render recruiting process details for review."""

    process = profile.setdefault("process", {})

    st.markdown("<div class='extraction-review-card'>", unsafe_allow_html=True)
    st.markdown(f"<h5>{html.escape(tr('Recruiting-Prozess', 'Recruiting process'))}</h5>", unsafe_allow_html=True)

    process["application_instructions"] = st.text_area(
        tr("Bewerbungshinweise", "Application instructions"),
        value=process.get("application_instructions", ""),
        key=ProfilePaths.PROCESS_APPLICATION_INSTRUCTIONS,
        height=120,
    )
    _update_profile(
        ProfilePaths.PROCESS_APPLICATION_INSTRUCTIONS,
        process["application_instructions"],
    )

    phases = render_list_text_area(
        label=tr("Prozessphasen", "Process phases"),
        session_key=str(ProfilePaths.PROCESS_PHASES),
        items=process.get("phases"),
        height=120,
    )
    process["phases"] = phases
    _update_profile(ProfilePaths.PROCESS_PHASES, phases)

    interview_stages = st.number_input(
        tr("Interviewstufen (Anzahl)", "Interview stages (count)"),
        value=int(process.get("interview_stages") or 0),
        key=str(ProfilePaths.PROCESS_INTERVIEW_STAGES),
        min_value=0,
        step=1,
    )
    process["interview_stages"] = int(interview_stages)
    _update_profile(ProfilePaths.PROCESS_INTERVIEW_STAGES, process["interview_stages"])

    process_notes = st.text_area(
        tr("Weitere Hinweise", "Additional notes"),
        value=process.get("process_notes", ""),
        key=ProfilePaths.PROCESS_PROCESS_NOTES,
        height=110,
    )
    process["process_notes"] = process_notes
    _update_profile(ProfilePaths.PROCESS_PROCESS_NOTES, process_notes)

    st.markdown("</div>", unsafe_allow_html=True)


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
        cleaned = unique_normalized(values)
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
        period = _job_ad_get_value(data, "compensation.period") or ("Jahr" if is_de else "year")
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
                details_text = f"{percentage}% Home-Office" if is_de else f"{percentage}% remote"
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
        (field.label_de if is_de else field.label_en for field in JOB_AD_FIELDS if field.key == field_key),
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
                details_text = f"{percentage}% Home-Office" if is_de else f"{percentage}% remote"
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
    """Return a sanitized profile payload for job-ad generation."""

    if not isinstance(data, Mapping):
        return NeedAnalysisProfile().model_dump(mode="json")

    base = deepcopy(dict(data))
    base.pop("lang", None)
    profile = coerce_and_fill(base)
    return profile.model_dump(mode="json")


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

    profile_state = st.session_state.get(StateKeys.PROFILE)
    if isinstance(data, dict) and profile_state is not data:
        st.session_state[StateKeys.PROFILE] = data

    field = str(q.get("field", ""))
    if not field:
        return
    prompt = q.get("question", "")
    suggestions = [str(option).strip() for option in q.get("suggestions") or [] if str(option).strip()]
    key = f"fu_{field}"
    anchor = f"anchor_{key}"
    focus_sentinel = f"{key}_focus_pending"
    highlight_sentinel = f"{key}_highlight_pending"
    container = st.container()
    with container:
        st.markdown(f"<div id='{anchor}'></div>", unsafe_allow_html=True)
        st.markdown("<div class='wizard-followup-item'>", unsafe_allow_html=True)
    existing_value = get_in(data, field, None)
    if key not in st.session_state:
        if field in LIST_FOLLOWUP_FIELDS:
            st.session_state[key] = "\n".join(_normalize_list(existing_value))
        elif field in YES_NO_FOLLOWUP_FIELDS:
            st.session_state[key] = bool(existing_value)
        elif field in DATE_FOLLOWUP_FIELDS:
            default_date = _default_date(existing_value)
            st.session_state[key] = default_date
        else:
            st.session_state[key] = _string_or_empty(existing_value)
    if focus_sentinel not in st.session_state:
        st.session_state[focus_sentinel] = True
    if highlight_sentinel not in st.session_state:
        st.session_state[highlight_sentinel] = True
    ui_variant = q.get("ui_variant")
    description = q.get("description")
    if ui_variant in ("info", "warning") and description:
        getattr(container, ui_variant)(description)
    elif description:
        container.caption(description)
    priority = q.get("priority")
    question_text = prompt or tr("Antwort eingeben", "Enter response")
    with container:
        if priority == "critical":
            st.markdown(f"{REQUIRED_PREFIX}**{question_text}**")
        else:
            st.markdown(f"**{question_text}**")
    if suggestions:
        cols = container.columns(len(suggestions))
        for index, (col, option) in enumerate(zip(cols, suggestions)):
            with col:
                st.markdown("<div class='wizard-followup-chip'>", unsafe_allow_html=True)
                if st.button(option, key=f"{key}_opt_{index}"):
                    _apply_followup_suggestion(field, key, option)
                st.markdown("</div>", unsafe_allow_html=True)

    should_focus = bool(st.session_state.get(focus_sentinel, False))
    label_text = question_text
    processed_value: Any
    touched_key: str | None = None
    with container:
        if field in YES_NO_FOLLOWUP_FIELDS:
            touched_key = f"{key}_touched"
            if touched_key not in st.session_state:
                st.session_state[touched_key] = existing_value is not None

            def _mark_followup_touched() -> None:
                st.session_state[touched_key] = True

            value = st.checkbox(
                label_text,
                key=key,
                label_visibility="collapsed",
                on_change=_mark_followup_touched,
            )
            if st.session_state.get(touched_key):
                processed_value = bool(value)
            else:
                processed_value = None
        elif field in NUMBER_FOLLOWUP_FIELDS:
            numeric_default = _coerce_followup_number(existing_value)
            raw_state_value = st.session_state.get(key, numeric_default)
            numeric_initial = _coerce_followup_number(raw_state_value)
            value = st.number_input(
                label_text,
                key=key,
                value=float(numeric_initial),
                step=1.0,
                label_visibility="collapsed",
            )
            if isinstance(value, float) and value.is_integer():
                processed_value = int(value)
            else:
                processed_value = value
        elif field in DATE_FOLLOWUP_FIELDS:
            value = st.date_input(
                label_text,
                key=key,
                format="YYYY-MM-DD",
                label_visibility="collapsed",
            )
            processed_value = value.isoformat() if isinstance(value, date) else ""
        elif field in LIST_FOLLOWUP_FIELDS:
            text_value = st.text_area(
                label_text,
                key=key,
                label_visibility="collapsed",
                placeholder=tr(
                    "Bitte jede Angabe in einer eigenen Zeile ergänzen.",
                    "Add each entry on a separate line.",
                ),
                height=110,
            )
            processed_value = [line.strip() for line in text_value.splitlines() if line.strip()]
        else:
            processed_value = st.text_input(
                label_text,
                key=key,
                label_visibility="collapsed",
            )
        if should_focus:
            st.markdown(
                f"""
<script>
(function() {{
    const anchor = document.getElementById('{anchor}');
    if (!anchor) {{
        return;
    }}
    const wrapper = anchor.nextElementSibling;
    if (!wrapper) {{
        return;
    }}
    const input = wrapper.querySelector('input, textarea');
    if (input && document.activeElement !== input) {{
        input.focus({{preventScroll: true}});
    }}
}})();
</script>
""",
                unsafe_allow_html=True,
            )
            st.session_state[focus_sentinel] = False
        highlight_pending = st.session_state.get(highlight_sentinel, False)
        if highlight_pending:
            highlight_class = "fu-highlight" if priority == "critical" else "fu-highlight-soft"
            if priority == "critical":
                st.toast(
                    tr("Neue kritische Anschlussfrage", "New critical follow-up"),
                    icon="⚠️",
                )
            st.markdown(
                f"""
<script>
(function() {{
    const anchor = document.getElementById('{anchor}');
    if (!anchor) {{
        return;
    }}
    const wrapper = anchor.nextElementSibling;
    if (!wrapper) {{
        return;
    }}
    wrapper.classList.add('{highlight_class}');
    wrapper.scrollIntoView({{behavior:'smooth',block:'center'}});
}})();
</script>
""",
                unsafe_allow_html=True,
            )
            st.session_state[highlight_sentinel] = False
    widget_has_state = field in st.session_state
    if widget_has_state:
        if processed_value is None:
            st.session_state.pop(field, None)
        else:
            st.session_state[field] = processed_value
        _update_profile(field, processed_value, session_value=processed_value)
    else:
        _update_profile(field, processed_value)
    if isinstance(data, dict):
        set_in(data, field, processed_value)
    if followup_has_response(processed_value):
        st.session_state.pop(focus_sentinel, None)
        st.session_state.pop(highlight_sentinel, None)
        if touched_key is not None:
            st.session_state.pop(touched_key, None)
    container.markdown("</div>", unsafe_allow_html=True)


def _render_followups_for_section(prefixes: Iterable[str], data: dict) -> None:
    """Render heading and follow-up questions matching ``prefixes``."""

    followups = [
        q
        for q in st.session_state.get(StateKeys.FOLLOWUPS, [])
        if any(q.get("field", "").startswith(p) for p in prefixes)
    ]
    if followups:
        _ensure_followup_styles()
        with st.container():
            st.markdown("<div class='wizard-followup-card'>", unsafe_allow_html=True)
            st.markdown(
                tr(
                    "Der Assistent hat Anschlussfragen, um fehlende Angaben zu ergänzen:",
                    "The assistant has generated follow-up questions to help fill in missing info:",
                )
            )
            st.markdown(
                tr(
                    "<p class='wizard-followup-meta'>Antworten werden automatisch gespeichert und im Profil gespiegelt.</p>",
                    "<p class='wizard-followup-meta'>Answers are saved automatically and synced with the profile.</p>",
                ),
                unsafe_allow_html=True,
            )
            if st.session_state.get(StateKeys.RAG_CONTEXT_SKIPPED):
                st.caption(
                    tr(
                        "Kontextvorschläge benötigen eine konfigurierte Vector-DB (VECTOR_STORE_ID).",
                        "Contextual suggestions require a configured vector store (VECTOR_STORE_ID).",
                    )
                )
            for q in list(followups):
                _render_followup_question(q, data)
            st.markdown("</div>", unsafe_allow_html=True)


def _render_followups_for_step(page_key: str, data: dict) -> None:
    """Render inline follow-ups configured for ``page_key``."""

    prefixes = PAGE_FOLLOWUP_PREFIXES.get(page_key)
    if not prefixes:
        return
    _render_followups_for_section(prefixes, data)


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


def _select_lang_suggestions(pair: LangSuggestionPair | None, lang: str | None) -> list[str]:
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

    extraction_missing = st.session_state.get(StateKeys.EXTRACTION_MISSING)
    computed_missing = get_missing_critical_fields()
    if extraction_missing:
        missing = list(dict.fromkeys((*extraction_missing, *computed_missing)))
    else:
        missing = computed_missing
    section_missing = [field for field in missing if FIELD_SECTION_MAP.get(field) == section_index]
    for field in section_missing:
        _ensure_targeted_followup(field)
    return section_missing


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
        st.session_state.get(StateKeys.INTERVIEW_AUDIENCE) or st.session_state.get(UIKeys.AUDIENCE_SELECT) or "general"
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


def _iter_profile_scalars(data: Mapping[str, Any], prefix: str = "") -> Iterable[tuple[str, Any]]:
    """Yield dot-paths for scalar values within ``data``."""

    for key, value in (data or {}).items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            yield from _iter_profile_scalars(value, path)
        elif isinstance(value, (list, tuple, set, frozenset)):
            continue
        else:
            yield path, value


def _prime_widget_state_from_profile(data: Mapping[str, Any]) -> None:
    """Synchronise Streamlit widget state from ``data``."""

    for path, value in _iter_profile_scalars(data):
        normalized = _normalize_semantic_empty(value)
        if normalized is None:
            st.session_state.pop(path, None)
        else:
            st.session_state[path] = value


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
    confidence_raw = entry.get("confidence")
    confidence: float | None
    if isinstance(confidence_raw, (int, float)):
        confidence = float(confidence_raw)
    elif isinstance(confidence_raw, str):
        try:
            confidence = float(confidence_raw)
        except ValueError:  # pragma: no cover - defensive
            confidence = None
    else:
        confidence = None
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
        confidence=confidence,
        is_inferred=is_inferred,
        url=url,
    )


def _summary_source_icon_html(path: str) -> str:
    """Return HTML snippet for the summary info icon."""

    info = _resolve_field_source_info(path)
    if not info:
        return ""
    tooltip = html.escape(info.tooltip(), quote=True)
    return f"<span class='summary-source-icon' role='img' aria-label='{tooltip}' title='{tooltip}'>ℹ️</span>"


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


def _apply_field_lock_kwargs(config: FieldLockConfig, base_kwargs: Mapping[str, Any] | None = None) -> dict[str, Any]:
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

    # Historically, high-confidence values were locked behind an explicit
    # "Edit value" toggle. The wizard should now present all fields as
    # directly editable while still surfacing confidence context. We keep the
    # high confidence and provenance indicators but skip the locking behaviour
    # entirely so the widgets render in an enabled state by default.

    source_info = _resolve_field_source_info(path)

    icons: list[str] = []
    if confidence_icon:
        icons.append(confidence_icon)
    if source_info:
        icons.append("ℹ️")
    icon_prefix = " ".join(filter(None, icons))
    label_with_icon = f"{icon_prefix} {label}".strip() if icon_prefix else label

    help_bits: list[str] = []
    if confidence_message:
        help_bits.append(confidence_message)
    if source_info:
        descriptor_plain = source_info.descriptor
        descriptor_full = source_info.descriptor_with_context()
        if source_info.is_inferred and descriptor_plain:
            help_bits.append(
                tr(
                    "Von KI abgeleitet aus {source}",
                    "Inferred by AI from {source}",
                ).format(source=descriptor_plain)
            )
        source_descriptor = descriptor_full or descriptor_plain
        if source_descriptor:
            help_bits.append(tr("Quelle: {source}", "Source: {source}").format(source=source_descriptor))
        if source_info.confidence is not None:
            help_bits.append(
                tr(
                    "Vertrauen: {percent}%",
                    "Confidence: {percent}%",
                ).format(percent=round(float(source_info.confidence) * 100))
            )
        if source_info.snippet:
            help_bits.append(source_info.snippet)
        if source_info.url:
            help_bits.append(source_info.url)
    help_text = "\n\n".join(help_bits)

    config: FieldLockConfig = {"label": label_with_icon, "was_locked": False}
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

    config["unlocked"] = True
    return config


def _collect_combined_certificates(requirements: Mapping[str, Any]) -> list[str]:
    """Return combined certificate entries across legacy keys."""

    raw_values: list[str] = []
    if isinstance(requirements, Mapping):
        for key in ("certificates", "certifications"):
            items = requirements.get(key, [])
            if isinstance(items, Sequence) and not isinstance(items, (str, bytes, bytearray)):
                raw_values.extend(str(item) for item in items)
    return unique_normalized(raw_values)


def _set_requirement_certificates(requirements: dict[str, Any], values: Iterable[str]) -> None:
    """Synchronize certificate lists under both legacy keys."""

    normalized = unique_normalized(list(values))
    requirements["certificates"] = normalized
    requirements["certifications"] = list(normalized)


def _sanitize_esco_options(
    options: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """Return cleaned ESCO occupation metadata entries."""

    sanitized: list[dict[str, str]] = []
    if not options:
        return sanitized
    seen: set[str] = set()
    for raw in options:
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("preferredLabel") or "").strip()
        uri = str(raw.get("uri") or "").strip()
        group = str(raw.get("group") or "").strip()
        if not label and not uri:
            continue
        marker = uri or f"{label}|{group}"
        if marker in seen:
            continue
        seen.add(marker)
        sanitized.append({"preferredLabel": label, "uri": uri, "group": group})
    return sanitized


def _coerce_occupation_ids(raw_value: Any) -> list[str]:
    """Normalize session state data to a list of occupation identifiers."""

    if isinstance(raw_value, str):
        return [raw_value] if raw_value else []
    if isinstance(raw_value, (list, tuple, set, frozenset)):
        result: list[str] = []
        for item in raw_value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
        return result
    return []


def _write_occupation_to_profile(meta: Mapping[str, Any] | None) -> None:
    """Persist primary ESCO occupation metadata to profile and raw data."""

    label = str(meta.get("preferredLabel") or "").strip() if meta else None
    uri = str(meta.get("uri") or "").strip() if meta else None
    group = str(meta.get("group") or "").strip() if meta else None

    _update_profile(ProfilePaths.POSITION_OCCUPATION_LABEL, label or None)
    _update_profile(ProfilePaths.POSITION_OCCUPATION_URI, uri or None)
    _update_profile(ProfilePaths.POSITION_OCCUPATION_GROUP, group or None)

    raw_profile = st.session_state.get(StateKeys.EXTRACTION_RAW_PROFILE)
    if isinstance(raw_profile, dict):
        set_in(raw_profile, "position.occupation_label", label or None)
        set_in(raw_profile, "position.occupation_uri", uri or None)
        set_in(raw_profile, "position.occupation_group", group or None)
        st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = raw_profile


def _refresh_esco_skills(
    selections: Sequence[Mapping[str, Any]],
    *,
    lang: str,
) -> None:
    """Load essential skills for all selected occupations and store them."""

    aggregated: list[str] = []
    seen: set[str] = set()
    for entry in selections:
        if not isinstance(entry, Mapping):
            continue
        uri = str(entry.get("uri") or "").strip()
        if not uri:
            continue
        for skill in _cached_esco_skills(uri, lang=lang):
            cleaned = str(skill or "").strip()
            if not cleaned:
                continue
            marker = cleaned.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            aggregated.append(cleaned)
    normalized_aggregated = unique_normalized(aggregated)
    st.session_state[StateKeys.ESCO_SKILLS] = normalized_aggregated
    if not normalized_aggregated:
        st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []


def _apply_esco_selection(
    selected_ids: Sequence[str],
    options: Sequence[Mapping[str, Any]],
    *,
    lang: str,
) -> None:
    """Update session state based on selected ESCO occupations."""

    option_map: dict[str, Mapping[str, Any]] = {}
    for option in options:
        if not isinstance(option, Mapping):
            continue
        uri = str(option.get("uri") or "").strip()
        if uri:
            option_map[uri] = option

    resolved: list[dict[str, Any]] = []
    for uri in selected_ids:
        meta = option_map.get(uri)
        if meta:
            resolved.append(dict(meta))

    st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = resolved

    primary = resolved[0] if resolved else None
    _write_occupation_to_profile(primary)

    esco_opted_in = bool(st.session_state.get(StateKeys.REQUIREMENTS_ESCO_OPT_IN))
    if resolved and not esco_opted_in:
        st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True
        esco_opted_in = True
    if esco_opted_in:
        _refresh_esco_skills(resolved, lang=lang)
    else:
        st.session_state[StateKeys.ESCO_SKILLS] = []
        st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []


def _render_requirements_esco_search(
    position: Mapping[str, Any] | None,
    *,
    parent: DeltaGenerator | None = None,
    lang: str,
) -> None:
    """Render the ESCO occupation search controls for the requirements step."""

    container = parent.container() if parent is not None else st.container()
    default_query = ""
    if isinstance(position, Mapping):
        default_query = str(position.get("job_title") or "").strip()

    stored_query = st.session_state.get(UIKeys.REQUIREMENTS_OCC_SEARCH)
    if stored_query is None and default_query:
        st.session_state[UIKeys.REQUIREMENTS_OCC_SEARCH] = default_query

    search_label = tr("ESCO-Beruf suchen", "Search ESCO occupation", lang=lang)
    search_placeholder = tr("z. B. Data Scientist", "e.g. Data Scientist", lang=lang)
    search_help = tr(
        "Nach offiziellen ESCO-Berufsprofilen suchen, um Pflichtskills zu übernehmen.",
        "Search official ESCO occupation profiles to import essential skills.",
        lang=lang,
    )
    container.text_input(
        search_label,
        key=UIKeys.REQUIREMENTS_OCC_SEARCH,
        placeholder=search_placeholder,
        help=search_help,
    )

    button_label = tr("🔎 ESCO-Profile finden", "🔎 Find ESCO occupations", lang=lang)
    if container.button(
        button_label,
        key=UIKeys.REQUIREMENTS_OCC_SELECT,
        type="secondary",
        help=tr(
            "Aktualisiert die Vorschlagsliste mit Treffern aus dem ESCO-Katalog.",
            "Refresh the suggestions list with matches from the ESCO catalogue.",
            lang=lang,
        ),
    ):
        query = str(st.session_state.get(UIKeys.REQUIREMENTS_OCC_SEARCH, "") or "").strip()
        if not query:
            container.warning(
                tr(
                    "Bitte gib einen Jobtitel oder ein Stichwort ein.",
                    "Please enter a job title or keyword before searching.",
                    lang=lang,
                )
            )
            return
        try:
            with container.spinner(tr("Lade ESCO-Berufe…", "Loading ESCO occupations…", lang=lang)):
                options = _cached_esco_search(query, lang=lang, limit=8)
        except Exception as exc:  # pragma: no cover - defensive fallback
            if st.session_state.get("debug"):
                st.session_state["esco_search_error"] = str(exc)
            container.warning(
                tr(
                    "ESCO-Suche derzeit nicht verfügbar.",
                    "ESCO search is currently unavailable.",
                    lang=lang,
                )
            )
            return

        sanitized = _sanitize_esco_options(options)
        if sanitized:
            st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = sanitized
            available_ids = [
                str(entry.get("uri") or "").strip() for entry in sanitized if str(entry.get("uri") or "").strip()
            ]
            current_ids = [
                sid
                for sid in _coerce_occupation_ids(st.session_state.get(UIKeys.POSITION_ESCO_OCCUPATION))
                if sid in available_ids
            ]
            if not current_ids and available_ids:
                current_ids = [available_ids[0]]
            st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = current_ids
            _apply_esco_selection(current_ids, sanitized, lang=lang)
            container.success(
                tr(
                    "ESCO-Profile aktualisiert – Vorschläge sind im Skill-Board verfügbar.",
                    "ESCO occupations updated – suggestions are ready in the skill board.",
                    lang=lang,
                )
            )
        else:
            st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = []
            st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = []
            st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = []
            st.session_state[StateKeys.ESCO_SKILLS] = []
            st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []
            container.warning(
                tr(
                    "Keine passenden ESCO-Berufe gefunden.",
                    "No matching ESCO occupations found.",
                    lang=lang,
                )
            )


def _render_esco_occupation_selector(
    position: Mapping[str, Any] | None,
    *,
    parent: DeltaGenerator | None = None,
    compact: bool = False,
) -> None:
    """Render a picker for ESCO occupation suggestions."""

    raw_options = st.session_state.get(StateKeys.UI_ESCO_OCCUPATION_OPTIONS, []) or []
    options = [entry for entry in _sanitize_esco_options(raw_options) if entry.get("uri")]
    if not options:
        return

    lang_code = st.session_state.get("lang", "de") or "de"
    option_ids = [str(entry.get("uri") or "").strip() for entry in options]
    format_map = {
        option_id: f"{entry.get('preferredLabel', '')} — {entry.get('group', '')}".strip(" —")
        for option_id, entry in zip(option_ids, options)
    }

    selected_entries = st.session_state.get(StateKeys.ESCO_SELECTED_OCCUPATIONS, []) or []
    selected_ids = [
        str(entry.get("uri") or "").strip()
        for entry in selected_entries
        if isinstance(entry, Mapping) and str(entry.get("uri") or "").strip()
    ]

    if not selected_ids and isinstance(position, Mapping):
        current_uri = str(position.get("occupation_uri") or "").strip()
        if current_uri:
            selected_ids = [current_uri]

    selected_ids = [sid for sid in selected_ids if sid in option_ids]

    override_sentinel = object()
    override_raw = st.session_state.pop(StateKeys.UI_ESCO_OCCUPATION_OVERRIDE, override_sentinel)
    if override_raw is override_sentinel:
        widget_value = [
            sid
            for sid in _coerce_occupation_ids(st.session_state.get(UIKeys.POSITION_ESCO_OCCUPATION))
            if sid in option_ids
        ]
        if not widget_value:
            widget_value = list(selected_ids)
    else:
        widget_value = [sid for sid in _coerce_occupation_ids(override_raw) if sid in option_ids]

    st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = widget_value

    def _current_selection() -> list[str]:
        if StateKeys.UI_ESCO_OCCUPATION_OVERRIDE in st.session_state:
            return [
                sid
                for sid in _coerce_occupation_ids(st.session_state.get(StateKeys.UI_ESCO_OCCUPATION_OVERRIDE))
                if sid in option_ids
            ]
        return [
            sid
            for sid in _coerce_occupation_ids(st.session_state.get(UIKeys.POSITION_ESCO_OCCUPATION))
            if sid in option_ids
        ]

    container = parent.container() if parent is not None else st.container()
    render_target = container

    if compact:
        style_key = "ui.esco_selector.compact"
        if not st.session_state.get(style_key):
            st.markdown(
                """
                <style>
                    .esco-compact .chip-section-title {
                        margin-bottom: 0.25rem;
                        font-size: 0.85rem;
                    }
                    .esco-compact .chip-section-title--secondary {
                        color: #0f172a;
                        opacity: 0.85;
                    }
                    .esco-compact .stMultiSelect [data-baseweb="tag"] {
                        transform: scale(0.9);
                    }
                    .esco-compact .stMultiSelect div[data-baseweb="input"] {
                        min-height: 2.6rem;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )
            st.session_state[style_key] = True
        container.markdown("<div class='esco-compact'>", unsafe_allow_html=True)
        render_target = container.container()

    heading_size = "micro" if compact else "compact"
    render_section_heading(
        tr("ESCO-Berufe auswählen", "Select ESCO occupations"),
        size=heading_size,
        target=render_target,
        description=tr(
            "Wähle alle passenden ESCO-Profile, um Skills und Synonyme vorzubereiten.",
            "Select all relevant ESCO profiles to prepare skills and synonyms.",
        ),
    )

    def _on_change() -> None:
        current_ids = _current_selection()
        _apply_esco_selection(current_ids, options, lang=lang_code)

    selection_label = tr("Empfohlene Berufe", "Suggested occupations")
    render_target.caption(selection_label)

    render_target.multiselect(
        selection_label,
        options=option_ids,
        key=UIKeys.POSITION_ESCO_OCCUPATION,
        format_func=lambda value: format_map.get(value, value),
        on_change=_on_change,
        label_visibility="collapsed",
        placeholder=tr(
            "ESCO-Beruf suchen oder hinzufügen …",
            "Search or add ESCO occupations…",
        ),
    )

    selected_ids = list(st.session_state.get(UIKeys.POSITION_ESCO_OCCUPATION, []))
    selected_labels = [format_map.get(opt, opt) for opt in selected_ids]
    available_ids = [opt for opt in option_ids if opt not in selected_ids]
    available_labels = [format_map.get(opt, opt) for opt in available_ids]

    selected_title = tr("Ausgewählt", "Selected")
    available_title = tr("Weitere Optionen", "More options")

    selected_col, available_col = render_target.columns(2, gap="small" if compact else "large")

    with selected_col:
        header_cols = selected_col.columns([4, 1])
        with header_cols[0]:
            st.markdown(
                f"<p class='chip-section-title'>{selected_title}</p>",
                unsafe_allow_html=True,
            )
        if selected_labels:
            with header_cols[1]:
                if st.button(
                    "✕",
                    key="esco.occupations.clear",
                    help=tr("Alle entfernen", "Clear all"),
                    type="secondary",
                    width="stretch",
                ):
                    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OVERRIDE] = []
                    _on_change()
                    st.rerun()
            clicked_selected = render_chip_button_grid(
                selected_labels,
                key_prefix="esco.occupations.selected",
                button_type="primary",
                columns=3,
            )
            if clicked_selected is not None:
                removed_id = selected_ids[clicked_selected]
                new_selection = [sid for sid in selected_ids if sid != removed_id]
                st.session_state[StateKeys.UI_ESCO_OCCUPATION_OVERRIDE] = new_selection
                _on_change()
                st.rerun()
        else:
            selected_col.caption(tr("Noch keine Auswahl getroffen.", "No values selected yet."))

    with available_col:
        st.markdown(
            f"<p class='chip-section-title chip-section-title--secondary'>{available_title}</p>",
            unsafe_allow_html=True,
        )
        if available_labels:
            clicked_available = render_chip_button_grid(
                available_labels,
                key_prefix="esco.occupations.available",
                columns=3,
            )
            if clicked_available is not None:
                added_id = available_ids[clicked_available]
                new_selection = selected_ids + [added_id]
                st.session_state[StateKeys.UI_ESCO_OCCUPATION_OVERRIDE] = new_selection
                _on_change()
                st.rerun()
        elif not selected_labels:
            available_col.caption(tr("Keine weiteren Vorschläge verfügbar.", "No more suggestions available."))

    current_ids = _current_selection()
    _apply_esco_selection(current_ids, options, lang=lang_code)

    if compact:
        container.markdown("</div>", unsafe_allow_html=True)


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
    return unique_normalized(combined)


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
    return unique_normalized(synonyms)


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

    render_section_heading(
        tr("Boolean-Suche", "Boolean search"),
        size="compact",
        description=tr(
            "Stellen Sie den Suchstring aus Jobtitel, Synonymen und Skills zusammen.",
            "Assemble the search string from the job title, synonyms, and skills.",
        ),
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


def missing_keys(data: dict, critical: List[str], ignore: Optional[set[str]] = None) -> List[str]:
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
    return [k for k in critical if k not in ignore and ((k not in flat) or (flat[k] in (None, "", [], {})))]


# --- Step-Renderers ---
def _advance_from_onboarding() -> None:
    """Advance the wizard from the onboarding screen."""

    first_incomplete, _ = _update_section_progress()
    _request_scroll_to_top()
    st.session_state.pop(StateKeys.PENDING_INCOMPLETE_JUMP, None)
    if isinstance(first_incomplete, int):
        target = first_incomplete
    else:
        target = COMPANY_STEP_INDEX
    st.session_state[StateKeys.STEP] = target
    st.rerun()


def _inject_onboarding_source_styles() -> None:
    """Inject styling for the onboarding intro and source inputs once per session."""

    if st.session_state.get(ONBOARDING_SOURCE_STYLE_KEY):
        return

    st.session_state[ONBOARDING_SOURCE_STYLE_KEY] = True
    st.markdown(
        """
        <style>
            .onboarding-intro {
                font-size: 1rem;
                line-height: 1.55;
                margin: 1rem auto 1.75rem;
                max-width: 780px;
                text-align: left;
            }

            section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                + div[data-testid="stHorizontalBlock"] {
                justify-content: center;
                gap: clamp(1.25rem, 2vw, 2.5rem);
                margin: 0 auto;
                max-width: min(960px, 100%);
            }

            section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                + div[data-testid="stHorizontalBlock"] div[data-testid="column"] {
                flex: 1 1 0;
                min-width: 0;
            }

            section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                + div[data-testid="stHorizontalBlock"] div[data-testid="column"] > div {
                width: 100%;
            }

            section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                + div[data-testid="stHorizontalBlock"]
                div[data-testid="column"]
                div[data-testid="stTextInput"] > div > div,
            section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                + div[data-testid="stHorizontalBlock"]
                div[data-testid="column"]
                div[data-testid="stFileUploader"] > div {
                width: 100%;
            }

            @media (max-width: 960px) {
                section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                    + div[data-testid="stHorizontalBlock"] {
                    flex-wrap: wrap;
                }

                section.main div.block-container div[data-testid="stMarkdown"]:has(.onboarding-source-marker)
                    + div[data-testid="stHorizontalBlock"] div[data-testid="column"] {
                    flex: 1 1 100%;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _is_onboarding_locked() -> bool:
    """Return ``True`` when onboarding ingestion must stay locked."""

    return not is_llm_available()


def _step_onboarding(schema: dict) -> None:
    """Render onboarding with language toggle, intro, and ingestion options."""

    _maybe_run_extraction(schema)

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    profile = _get_profile_state()
    profile_context = _build_profile_context(profile)

    onboarding_header = _format_dynamic_message(
        default=(
            "Intelligenzgestützter Recruiting-Kickstart",
            "Intelligence-powered recruiting kickoff",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Intelligenzgestützter Recruiting-Kickstart für {job_title} bei {company_name}",
                    "Intelligence-powered recruiting kickoff for {job_title} at {company_name}",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Intelligenzgestützter Recruiting-Kickstart für {job_title}",
                    "Intelligence-powered recruiting kickoff for {job_title}",
                ),
                ("job_title",),
            ),
        ],
    )
    onboarding_caption = _format_dynamic_message(
        default=(
            "Teile den Einstieg über URL oder Datei und sichere jede relevante Insight gleich am Anfang.",
            "Share a URL or file to capture every crucial insight from the very first step.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Übermittle den Startpunkt für {job_title} bei {company_name} über URL oder Datei und sichere jede Insight.",
                    "Provide the entry point for {job_title} at {company_name} via URL or upload to secure every insight.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Übermittle den Startpunkt für {job_title} über URL oder Datei und sichere jede Insight.",
                    "Provide the entry point for the {job_title} role via URL or upload to secure every insight.",
                ),
                ("job_title",),
            ),
        ],
    )
    render_step_heading(onboarding_header, onboarding_caption)

    _inject_onboarding_source_styles()

    intro_lines = [
        tr(
            "Unstrukturierte Bedarfsklärung verbrennt gleich im ersten Schritt kostbare Recruiting-Insights.",
            "Unstructured intake burns expensive recruiting intelligence in the very first step.",
        ),
        tr(
            "Unsere OpenAI-API-Agents erfassen jedes Detail und strukturieren Anforderungen in Echtzeit.",
            "Our OpenAI API agents capture every nuance and structure requirements in real time.",
        ),
        tr(
            "ESCO-Skillgraph und Marktprofile liefern Kontext für Skills, Seniorität und Branchensprache.",
            "ESCO skill graphs and market profiles add context for skills, seniority, and industry language.",
        ),
        tr(
            "Ein dynamischer Info-Gathering-Prozess baut einen vollständigen Datensatz für diese Vakanz auf.",
            "A dynamic info gathering process assembles a complete dataset for this specific vacancy.",
        ),
        tr(
            "So entstehen Inputs für interne Kommunikations-Automation & Folgeschritte – Ziel: glückliche Kandidat:innen nachhaltig platzieren.",
            "These inputs fuel internal communication automation and downstream steps – goal: place happy candidates sustainably.",
        ),
    ]

    intro_html = "<br/>".join(intro_lines)
    st.markdown(f"<div class='onboarding-intro'>{intro_html}</div>", unsafe_allow_html=True)

    st.divider()

    if st.session_state.get("source_error"):
        fallback_message = tr(
            "Es gab ein Problem beim Import. Versuche URL oder Upload erneut oder kontaktiere unser Support-Team.",
            "There was an issue while importing the content. Retry the URL/upload or contact our support team.",
        )
        error_text = st.session_state.get("source_error_message") or fallback_message
        st.error(error_text)

    prefill = st.session_state.pop("__prefill_profile_text__", None)
    if prefill is not None:
        st.session_state[UIKeys.PROFILE_TEXT_INPUT] = prefill
        st.session_state[StateKeys.RAW_TEXT] = prefill
        doc_prefill = st.session_state.get("__prefill_profile_doc__")
        if doc_prefill:
            st.session_state[StateKeys.RAW_BLOCKS] = doc_prefill.blocks

    locked = _is_onboarding_locked()

    st.markdown(
        "<div class='onboarding-source-marker' style='display:none'></div>",
        unsafe_allow_html=True,
    )
    url_column, upload_column = st.columns(2, gap="large")
    with url_column:
        st.text_input(
            tr("Stellenanzeigen-URL einfügen", "Provide the job posting URL"),
            key=UIKeys.PROFILE_URL_INPUT,
            on_change=on_url_changed,
            placeholder=tr("Bitte URL eingeben", "Enter the job posting URL"),
            help=tr(
                "Die URL muss ohne Login erreichbar sein. Wir übernehmen den Inhalt automatisch.",
                "The URL needs to be accessible without authentication. We will fetch the content automatically.",
            ),
            disabled=locked,
        )

    with upload_column:
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
            disabled=locked,
        )

    _render_extraction_review()

    _render_followups_for_step("jobad", profile)

    if st.button(
        tr("Weiter ▶", "Next ▶"),
        type="primary",
        key="onboarding_next_compact",
        disabled=locked,
    ):
        _advance_from_onboarding()


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
    render_step_heading(company_header, company_caption)
    data = profile
    company = data.setdefault("company", {})
    position = data.setdefault("position", {})
    department = data.setdefault("department", {})
    team = data.setdefault("team", {})
    location_data = data.setdefault("location", {})
    combined_certificates = _collect_combined_certificates(data["requirements"])
    _set_requirement_certificates(data["requirements"], combined_certificates)
    missing_here = _missing_fields_for_section(1)

    label_company = tr(*COMPANY_NAME_LABEL)
    if "company.name" in missing_here:
        label_company += REQUIRED_SUFFIX
    company_lock = _field_lock_config(
        ProfilePaths.COMPANY_NAME,
        label_company,
        container=st,
        context="step",
    )
    company_kwargs = _apply_field_lock_kwargs(
        company_lock,
        {"help": tr(*COMPANY_NAME_HELP)},
    )

    company_identity_container = st.container()

    _render_company_research_tools(company.get("website", ""))

    with company_identity_container:
        company["name"] = widget_factory.text_input(
            ProfilePaths.COMPANY_NAME,
            company_lock["label"],
            placeholder=tr(*COMPANY_NAME_PLACEHOLDER),
            value_formatter=_string_or_empty,
            **company_kwargs,
        )
        if ProfilePaths.COMPANY_NAME in missing_here and not company["name"]:
            st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

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
        tr(*COMPANY_CONTACT_NAME_LABEL),
        widget_factory=contact_cols[0].text_input,
        placeholder=tr(*COMPANY_CONTACT_NAME_PLACEHOLDER),
        value_formatter=_string_or_empty,
    )
    contact_email_label = tr(*COMPANY_CONTACT_EMAIL_LABEL)
    contact_email_key = str(ProfilePaths.COMPANY_CONTACT_EMAIL)
    contact_email_state = st.session_state.get(contact_email_key)
    contact_email_missing = contact_email_key in missing_here or not (
        isinstance(contact_email_state, str) and contact_email_state.strip()
    )
    if contact_email_missing:
        contact_email_label += REQUIRED_SUFFIX
    contact_email_value = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        contact_email_label,
        widget_factory=contact_cols[1].text_input,
        placeholder=tr(*COMPANY_CONTACT_EMAIL_PLACEHOLDER),
        value_formatter=_string_or_empty,
        allow_callbacks=False,
        sync_session_state=False,
    )
    contact_cols[1].caption(tr(*COMPANY_CONTACT_EMAIL_CAPTION))
    _, contact_email_error = persist_contact_email(contact_email_value)
    if contact_email_error:
        contact_cols[1].error(tr(*contact_email_error))
    phone_label = tr(*COMPANY_CONTACT_PHONE_LABEL)
    if ProfilePaths.COMPANY_CONTACT_PHONE in missing_here:
        phone_label += REQUIRED_SUFFIX
    contact_phone = widget_factory.text_input(
        ProfilePaths.COMPANY_CONTACT_PHONE,
        phone_label,
        widget_factory=contact_cols[2].text_input,
        placeholder=tr(*COMPANY_CONTACT_PHONE_PLACEHOLDER),
        value_formatter=_string_or_empty,
    )
    if ProfilePaths.COMPANY_CONTACT_PHONE in missing_here and not (contact_phone or "").strip():
        contact_cols[2].caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    city_col, country_col = st.columns(2, gap="small")
    city_label = tr(*PRIMARY_CITY_LABEL)
    primary_city_key = str(ProfilePaths.LOCATION_PRIMARY_CITY)
    primary_city_state = st.session_state.get(primary_city_key)
    city_missing = primary_city_key in missing_here or not (
        isinstance(primary_city_state, str) and primary_city_state.strip()
    )
    if city_missing:
        city_label += REQUIRED_SUFFIX
    city_lock = _field_lock_config(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        city_label,
        container=city_col,
        context="step",
    )
    city_kwargs = _apply_field_lock_kwargs(city_lock)
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
    city_col.caption(tr(*PRIMARY_CITY_CAPTION))
    _, primary_city_error = persist_primary_city(city_value_input)
    if primary_city_error:
        city_col.error(tr(*primary_city_error))

    country_label = tr(*PRIMARY_COUNTRY_LABEL)
    if ProfilePaths.LOCATION_COUNTRY in missing_here:
        country_label += REQUIRED_SUFFIX
    country_lock = _field_lock_config(
        ProfilePaths.LOCATION_COUNTRY,
        country_label,
        container=country_col,
        context="step",
    )
    country_kwargs = _apply_field_lock_kwargs(country_lock)
    location_data["country"] = widget_factory.text_input(
        ProfilePaths.LOCATION_COUNTRY,
        country_lock["label"],
        widget_factory=country_col.text_input,
        placeholder=tr(*PRIMARY_COUNTRY_PLACEHOLDER),
        value_formatter=_string_or_empty,
        **country_kwargs,
    )
    if ProfilePaths.LOCATION_COUNTRY in missing_here and not location_data.get("country"):
        country_col.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

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

        existing_selection = _filter_phase_indices(person.get("information_loop_phases", []), len(phase_indices))
        if existing_selection != person.get("information_loop_phases"):
            person["information_loop_phases"] = existing_selection
            if phase_indices:
                label_pairs = [
                    (
                        str(index),
                        _phase_label_formatter(phase_labels)(index),
                    )
                    for index in phase_indices
                ]
                selected_phase_strings = [str(index) for index in existing_selection]
            chosen_phase_values = chip_multiselect_mapped(
                tr("Informationsloop-Phasen", "Information loop phases"),
                option_pairs=label_pairs,
                values=selected_phase_strings,
                help_text=tr(
                    "Wähle die Phasen, in denen dieser Kontakt informiert wird.",
                    "Select the process phases where this contact stays in the loop.",
                ),
                state_key=f"{key_prefix}.{idx}.info_loop",
                add_more_hint=ADD_MORE_INFO_LOOP_PHASES_HINT,
            )
            person["information_loop_phases"] = [int(value) for value in chosen_phase_values if str(value).isdigit()]
        else:
            person["information_loop_phases"] = []
        if not phase_indices:
            st.caption(
                tr(
                    "Füge unten Phasen hinzu, um Kontakte dem Informationsloop zuzuordnen.",
                    "Add process phases below to assign contacts to the information loop.",
                )
            )

    has_primary = any(p.get("primary") for p in stakeholders)
    if stakeholders and not has_primary:
        st.warning(
            tr(
                "Bitte bestätige, wer der primäre Kontakt sein soll, bevor wir automatisch einen auswählen.",
                "Please confirm who should be the primary contact before we auto-select one.",
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
            phase["name"] = text_input_with_state(
                tr("Phasen-Name", "Phase name"),
                target=phase,
                field="name",
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
                width="stretch",
            )
            phase_participants = _filter_existing_participants(phase.get("participants", []), stakeholder_names)
            participant_pairs = [(name, name) for name in stakeholder_names if isinstance(name, str) and name]
            phase["participants"] = chip_multiselect_mapped(
                tr("Beteiligte", "Participants"),
                option_pairs=participant_pairs,
                values=phase_participants,
                state_key=f"{key_prefix}.{idx}.participants",
                add_more_hint=ADD_MORE_PARTICIPANTS_HINT,
            )
            phase["docs_required"] = text_input_with_state(
                tr("Benötigte Unterlagen/Assignments", "Required docs/assignments"),
                target=phase,
                field="docs_required",
                key=f"{key_prefix}.{idx}.docs",
            )
            phase["assessment_tests"] = st.checkbox(
                tr("Assessment/Test", "Assessment/test"),
                value=phase.get("assessment_tests", False),
                key=f"{key_prefix}.{idx}.assessment",
            )
            phase["timeframe"] = text_input_with_state(
                tr("Geplanter Zeitrahmen", "Timeframe"),
                target=phase,
                field="timeframe",
                key=f"{key_prefix}.{idx}.timeframe",
            )


def _render_onboarding_section(process: dict, key_prefix: str, *, allow_generate: bool = True) -> None:
    """Render onboarding suggestions with optional LLM generation."""

    lang = st.session_state.get("lang", "de")
    profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
    existing_entries = _split_onboarding_entries(process.get("onboarding_process", ""))

    job_title_state_value = st.session_state.get("position.job_title", "")
    job_title = str(job_title_state_value or "").strip()
    if not job_title and isinstance(profile, Mapping):
        job_title = str((profile.get("position") or {}).get("job_title") or "").strip()

    if allow_generate:
        llm_available = is_llm_available()
        if not job_title:
            st.info(
                tr(
                    "Bitte gib einen Jobtitel ein, um Onboarding-Vorschläge zu erstellen.",
                    "Please provide a job title to generate onboarding suggestions.",
                )
            )
        if not llm_available:
            st.caption(llm_disabled_message())
        generate_clicked = st.button(
            "🤖 " + tr("Onboarding-Vorschläge generieren", "Generate onboarding suggestions"),
            key=f"{key_prefix}.generate",
            disabled=not job_title or not llm_available,
        )
        if generate_clicked and job_title and llm_available:
            company_data = profile.get("company") if isinstance(profile, Mapping) else {}
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
                tone_style=st.session_state.get(UIKeys.TONE_SELECT),
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
                selection_key = f"{key_prefix}.selection"
                combined_selection = list(dict.fromkeys(existing_entries + suggestions))
                st.session_state[selection_key] = combined_selection
                st.session_state[StateKeys.ONBOARDING_SUGGESTIONS] = suggestions
                st.rerun()

    current_suggestions = st.session_state.get(StateKeys.ONBOARDING_SUGGESTIONS, []) or []
    options = list(dict.fromkeys(current_suggestions + existing_entries))
    defaults = [opt for opt in options if opt in existing_entries]
    selected = chip_multiselect(
        tr("Onboarding-Prozess", "Onboarding process"),
        options=options,
        values=defaults,
        help_text=tr(
            "Wähle die Vorschläge aus, die in den Onboarding-Prozess übernommen werden sollen.",
            "Select the suggestions you want to include in the onboarding process.",
        ),
        add_more_hint=ADD_MORE_ONBOARDING_HINT,
        state_key=str(ProfilePaths.PROCESS_ONBOARDING_PROCESS),
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


def _step_position() -> None:
    """Render the position details step.",

    Returns:
        None
    """

    profile = _get_profile_state()
    title, subtitle, intros = _resolve_step_copy("team", profile)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)
    data = profile
    data.setdefault("company", {})
    position = data.setdefault("position", {})
    data.setdefault("location", {})
    meta_data = data.setdefault("meta", {})
    employment = data.setdefault("employment", {})

    missing_here = _missing_fields_for_section(2)

    render_section_heading(tr("Team & Kontext", "Team & context"))
    role_cols = st.columns((1.3, 1))
    title_label = tr("Jobtitel", "Job title")
    if "position.job_title" in missing_here:
        title_label += REQUIRED_SUFFIX
    title_lock = _field_lock_config(
        ProfilePaths.POSITION_JOB_TITLE,
        title_label,
        container=role_cols[0],
        context="step",
    )
    job_title_kwargs = _apply_field_lock_kwargs(title_lock)
    position["job_title"] = widget_factory.text_input(
        ProfilePaths.POSITION_JOB_TITLE,
        title_lock["label"],
        widget_factory=role_cols[0].text_input,
        placeholder=tr("Jobtitel eingeben", "Enter the job title"),
        value_formatter=_string_or_empty,
        **job_title_kwargs,
    )
    _update_profile(ProfilePaths.POSITION_JOB_TITLE, position["job_title"])
    if ProfilePaths.POSITION_JOB_TITLE in missing_here and not position.get("job_title"):
        role_cols[0].caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    _render_esco_occupation_selector(position)

    position["seniority_level"] = widget_factory.text_input(
        ProfilePaths.POSITION_SENIORITY,
        tr("Seniorität", "Seniority"),
        widget_factory=role_cols[1].text_input,
        placeholder=tr("Karrierestufe angeben", "Enter the seniority level"),
        value_formatter=_string_or_empty,
    )

    manager_cols = st.columns((1, 1))
    position["reporting_manager_name"] = widget_factory.text_input(
        ProfilePaths.POSITION_REPORTING_MANAGER_NAME,
        tr("Vorgesetzte Person", "Reporting manager"),
        widget_factory=manager_cols[0].text_input,
        placeholder=tr(
            "Name der vorgesetzten Person eintragen",
            "Enter the reporting manager's name",
        ),
        value_formatter=_string_or_empty,
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
    summary_label = tr(*ROLE_SUMMARY_LABEL)
    if ProfilePaths.POSITION_ROLE_SUMMARY in missing_here:
        summary_label += REQUIRED_SUFFIX
    position["role_summary"] = st.text_area(
        summary_label,
        value=st.session_state.get(ProfilePaths.POSITION_ROLE_SUMMARY, position.get("role_summary", "")),
        height=120,
        key=ProfilePaths.POSITION_ROLE_SUMMARY,
    )
    if ProfilePaths.POSITION_ROLE_SUMMARY in missing_here and not position.get("role_summary"):
        st.caption(tr("Dieses Feld ist erforderlich", "This field is required"))

    render_section_heading(tr("Zeitplan", "Timing"), icon="⏱️", size="compact")

    timing_cols = st.columns(3)
    target_start_default = _default_date(meta_data.get("target_start_date"))
    start_selection = timing_cols[0].date_input(
        tr("Gewünschtes Startdatum", "Desired start date"),
        value=target_start_default,
        format="YYYY-MM-DD",
    )
    meta_data["target_start_date"] = start_selection.isoformat() if isinstance(start_selection, date) else ""

    application_deadline_default = _default_date(meta_data.get("application_deadline"))
    deadline_selection = timing_cols[1].date_input(
        tr("Bewerbungsschluss", "Application deadline"),
        value=application_deadline_default,
        format="YYYY-MM-DD",
    )
    meta_data["application_deadline"] = deadline_selection.isoformat() if isinstance(deadline_selection, date) else ""

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
    schedule_cols = st.columns(3)
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

    # Inline follow-up questions for Position, Location and Employment section
    _render_followups_for_step("team", data)


def _step_requirements() -> None:
    """Render the requirements step for skills and certifications."""

    data = _get_profile_state()
    title, subtitle, intros = _resolve_step_copy("role_tasks", data)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)
    location_data = data.setdefault("location", {})

    raw_requirements = data.get("requirements")
    if isinstance(raw_requirements, dict):
        requirements: dict[str, Any] = raw_requirements
    else:
        requirements = {}
        data["requirements"] = requirements

    esco_opted_in = bool(st.session_state.get(StateKeys.REQUIREMENTS_ESCO_OPT_IN))
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = esco_opted_in

    requirements_style_key = "ui.requirements_styles"
    if not st.session_state.get(requirements_style_key):
        st.markdown(
            """
            <style>
            .requirement-panel {
                border-radius: 0.9rem;
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
                background: var(--surface-1, #f1f5f9);
                padding: 1.25rem 1.4rem;
                margin-bottom: 1.2rem;
            }
            .requirement-panel--insights {
                background: var(--surface-accent-soft, rgba(47, 216, 197, 0.18));
                border: 1px solid var(
                    --interactive-border-strong,
                    rgba(87, 182, 255, 0.28)
                );
                box-shadow: inset 0 0 0 1px var(
                    --surface-accent-strong,
                    rgba(47, 149, 241, 0.16)
                );
            }
            .requirement-panel__header {
                display: flex;
                gap: 0.5rem;
                align-items: center;
                font-weight: 600;
                font-size: 1.05rem;
            }
            .requirement-panel__caption {
                color: var(--tone-200, #d4d4d8);
                margin: 0.15rem 0 0.95rem 0;
                font-size: 0.92rem;
            }
            .requirement-panel--insights .requirement-panel__caption {
                color: var(--tone-100, #e2e8f0);
            }
            .requirement-panel__icon {
                font-size: 1.1rem;
            }
            .requirement-panel--insights .requirement-panel__icon {
                font-size: 0.95rem;
            }
            .ai-suggestion-box {
                margin-top: 0.6rem;
                padding: 0.75rem 0.85rem;
                border-radius: 0.75rem;
                border: 1px dashed var(--interactive-border-strong, rgba(14, 165, 233, 0.6));
                background: var(--surface-accent-soft, #f1f5f9);
            }
            .ai-suggestion-box__title {
                font-weight: 600;
                margin-bottom: 0.3rem;
            }
            .ai-suggestion-box__caption {
                font-size: 0.85rem;
                color: var(--accent, #0369a1);
                margin-bottom: 0.5rem;
            }
            .skill-suggestion-table {
                margin-top: 0.75rem;
            }
            .skill-suggestion-table [data-testid="stDataFrame"] {
                border-radius: 0.75rem;
                border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.35));
                background: var(--surface-0, #f8fafc);
                overflow: hidden;
            }
            .skill-suggestion-table table {
                font-size: 0.92rem;
            }
            .skill-suggestion-table [data-baseweb="checkbox"] {
                transform: scale(0.92);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state[requirements_style_key] = True

    lang = st.session_state.get("lang", "en")
    focus_presets = _SKILL_FOCUS_PRESETS.get(lang, _SKILL_FOCUS_PRESETS["en"])
    stored_focus = list(st.session_state.get(StateKeys.SKILL_SUGGESTION_HINTS, []))
    focus_options = sorted(
        {value.strip() for value in (focus_presets or []) if value.strip()}.union(
            {value.strip() for value in stored_focus if value.strip()}
        ),
        key=str.casefold,
    )

    job_title = (data.get("position", {}).get("job_title", "") or "").strip()
    has_missing_key = bool(st.session_state.get("openai_api_key_missing"))

    def _load_skill_suggestions(
        focus_terms: Sequence[str],
    ) -> tuple[dict[str, dict[str, list[str]]], str | None, str | None]:
        local_store = st.session_state.get(StateKeys.SKILL_SUGGESTIONS, {}) or {}
        focus_signature_local = tuple(sorted(focus_terms, key=str.casefold))
        if job_title and not has_missing_key:
            stored_title = str(local_store.get("_title") or "")
            stored_lang = str(local_store.get("_lang") or "")
            stored_focus = tuple(str(item) for item in local_store.get("_focus", []))
            if stored_title == job_title and stored_lang == lang and stored_focus == focus_signature_local:
                payload: dict[str, dict[str, list[str]]] = {}
                for field in (
                    "hard_skills",
                    "soft_skills",
                    "tools_and_technologies",
                    "certificates",
                ):
                    raw_groups = local_store.get(field)
                    if not isinstance(raw_groups, Mapping):
                        continue
                    cleaned_groups: dict[str, list[str]] = {}
                    for group_name, values in raw_groups.items():
                        if not isinstance(group_name, str):
                            continue
                        cleaned_values = [
                            str(value).strip()
                            for value in (values or [])
                            if isinstance(value, str) and str(value).strip()
                        ]
                        if cleaned_values:
                            cleaned_groups[group_name] = cleaned_values
                    if cleaned_groups:
                        payload[field] = cleaned_groups
                cached_error = str(local_store.get("_error") or "") or None
                return payload, cached_error, None
            if local_store:
                st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
                st.session_state.pop("skill_suggest_error", None)
        if has_missing_key:
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.session_state.pop("skill_suggest_error", None)
            return {}, None, "missing_key"
        if not job_title:
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.session_state.pop("skill_suggest_error", None)
            return {}, None, "missing_title"
        return {}, None, "fetch_required"

    def _show_suggestion_warning(error: str | None) -> None:
        if not error:
            return
        if st.session_state.get("debug"):
            st.session_state["skill_suggest_error"] = error
        st.warning(
            tr(
                "Skill-Vorschläge nicht verfügbar (API-Fehler)",
                "Skill suggestions not available (API error)",
            )
        )

    raw_position = data.get("position")
    position_mapping: Mapping[str, Any] | None = raw_position if isinstance(raw_position, Mapping) else None

    def _collect_existing_requirement_terms() -> list[str]:
        collected: list[str] = []
        source_keys = (
            "hard_skills_required",
            "hard_skills_optional",
            "soft_skills_required",
            "soft_skills_optional",
            "tools_and_technologies",
            "certificates",
        )
        for key_name in source_keys:
            for entry in requirements.get(key_name, []) or []:
                if not isinstance(entry, str):
                    continue
                cleaned = entry.strip()
                if cleaned:
                    collected.append(cleaned)
        return collected

    helper_columns = st.columns((2.5, 1.5), gap="large")
    with helper_columns[0]:
        focus_selection = chip_multiselect(
            tr("Fokus für KI-Skill-Vorschläge", "Focus for AI skill suggestions"),
            options=focus_options,
            values=stored_focus,
            help_text=tr(
                "Gib Themenfelder vor, damit die KI passende Skills priorisiert.",
                "Provide focus areas so the AI can prioritise matching skills.",
            ),
            dropdown=True,
            add_more_hint=ADD_MORE_SKILL_FOCUS_HINT,
            state_key=StateKeys.SKILL_SUGGESTION_HINTS,
        )
        disabled_hints: list[str] = []
        if has_missing_key:
            disabled_hints.append(llm_disabled_message())
        if not job_title:
            disabled_hints.append(
                tr(
                    "Bitte gib einen Jobtitel an, um Skill-Vorschläge zu erhalten.",
                    "Provide a job title to unlock skill suggestions.",
                )
            )
        for hint in disabled_hints:
            st.caption(hint)
        if st.button(
            "💡 " + tr("KI-Skills vorschlagen", "Suggest additional skills"),
            key=UIKeys.REQUIREMENTS_FETCH_AI_SUGGESTIONS,
            type="primary",
            help=tr(
                "Lässt die KI zusätzliche passende Skills vorschlagen.",
                "Ask the AI for additional relevant skills.",
            ),
            disabled=bool(disabled_hints),
        ):
            focus_signature_local = tuple(sorted(focus_selection, key=str.casefold))
            existing_terms = _collect_existing_requirement_terms()
            responsibility_items = [
                str(item).strip()
                for item in (data.get("responsibilities", {}) or {}).get("items", [])
                if isinstance(item, str) and str(item).strip()
            ]
            spinner_label = tr(
                "Generiere Skill-Vorschläge…",
                "Generating skill suggestions…",
                lang=lang,
            )
            with st.spinner(spinner_label):
                fetched, error = get_skill_suggestions(
                    job_title,
                    lang=lang,
                    focus_terms=list(focus_selection),
                    tone_style=st.session_state.get(UIKeys.TONE_SELECT),
                    existing_skills=existing_terms,
                    responsibilities=responsibility_items,
                )
                normalized_payload: dict[str, dict[str, list[str]]] = {}
                for field, groups in fetched.items():
                    if not isinstance(groups, Mapping):
                        continue
                    field_groups: dict[str, list[str]] = {}
                    for group, values in groups.items():
                        if not isinstance(group, str):
                            continue
                        cleaned_values = [
                            str(value).strip()
                            for value in (values or [])
                            if isinstance(value, str) and str(value).strip()
                        ]
                        if cleaned_values:
                            field_groups[group] = cleaned_values
                    if field_groups:
                        normalized_payload[field] = field_groups
                st.session_state[StateKeys.SKILL_SUGGESTIONS] = {
                    "_title": job_title,
                    "_lang": lang,
                    "_focus": list(focus_signature_local),
                    "_error": error,
                    **normalized_payload,
                }
                if error:
                    if st.session_state.get("debug"):
                        st.session_state["skill_suggest_error"] = error
                else:
                    st.session_state.pop("skill_suggest_error", None)
                if not normalized_payload and not error:
                    st.info(
                        tr(
                            "Keine neuen Skill-Ideen gefunden – passe Fokus oder vorhandene Anforderungen an.",
                            "No new skill ideas found – adjust the focus tags or existing requirements.",
                        )
                    )

    with helper_columns[1]:
        lang_code = st.session_state.get("lang", "de") or "de"
        _render_requirements_esco_search(position_mapping, lang=lang_code)
        _render_esco_occupation_selector(position_mapping, compact=True)
        current_esco_opt_in = bool(st.session_state.get(StateKeys.REQUIREMENTS_ESCO_OPT_IN))
        esco_button_label = (
            tr("🌐 ESCO-Vorschläge laden", "🌐 Fetch suggestions from ESCO")
            if not current_esco_opt_in
            else tr("🔌 ESCO-Vorschläge deaktivieren", "🔌 Disable ESCO suggestions")
        )
        if st.button(
            esco_button_label,
            key=UIKeys.REQUIREMENTS_FETCH_ESCO_SUGGESTIONS,
            type="secondary",
            help=tr(
                "Steuert, ob ESCO-Empfehlungen im Skill-Board erscheinen.",
                "Control whether ESCO recommendations appear on the skill board.",
            ),
        ):
            new_value = not current_esco_opt_in
            st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = new_value
            if not new_value:
                st.session_state[StateKeys.ESCO_SKILLS] = []
                st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []
            st.rerun()

    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = focus_selection
    suggestions, suggestions_error, suggestion_hint = _load_skill_suggestions(focus_selection)
    _show_suggestion_warning(suggestions_error)

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

    missing_here = _missing_fields_for_section(3)

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
        variant: str | None = None,
    ) -> Iterator[None]:
        if parent is not None:
            panel_container = parent.container()
        else:
            panel_container = st.container()
        panel_classes = ["requirement-panel"]
        if variant:
            panel_classes.append(f"requirement-panel--{variant}")
        class_attr = " ".join(panel_classes)
        panel_container.markdown(
            f"<div class='{class_attr}' title='{html.escape(tooltip)}'>",
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
        if suggestion_hint == "fetch_required":
            if show_hint:
                st.info(
                    tr(
                        "Klicke auf „KI-Skills vorschlagen“, um neue Ideen abzurufen.",
                        "Press “Suggest additional skills” to request fresh ideas.",
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

        grouped_pool = suggestions.get(source_key, {}) or {}
        seen_grouped: set[tuple[str, str]] = set()
        option_entries: list[tuple[str, str, str]] = []
        lang_code = st.session_state.get("lang", "de")
        for group_key, values in grouped_pool.items():
            label_key = _SUGGESTION_GROUP_LABEL_KEYS.get(group_key)
            if label_key:
                label_prefix = translate_key(label_key, lang_code)
            else:
                label_prefix = group_key.title()
            for raw in values:
                cleaned = str(raw or "").strip()
                if not cleaned:
                    continue
                marker = cleaned.casefold()
                if marker in existing_terms:
                    continue
                marker_key = (group_key, marker)
                if marker_key in seen_grouped:
                    continue
                seen_grouped.add(marker_key)
                option_entries.append((group_key, cleaned, label_prefix))

        if not option_entries:
            if show_hint:
                st.caption(
                    tr(
                        "Aktuell keine Vorschläge verfügbar – bitte KI-Vorschläge aktivieren, einen gültigen API-Schlüssel hinterlegen und den Jobtitel ausfüllen. Wenn bereits alle Optionen übernommen sind, kannst du die Liste aktualisieren.",
                        "No suggestions available right now – make sure AI suggestions are enabled, a valid API key is configured, and the job title is set. If you've already taken every option, try refreshing.",
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
        formatted_options = sorted(
            option_entries,
            key=lambda item: (item[2].casefold(), item[1].casefold()),
        )
        selection_label = tr("Vorschläge auswählen", "Select suggestions")
        st.markdown(f"**{selection_label}**")
        st.caption(
            tr(
                "Klicke auf eine Box, um den Vorschlag zu übernehmen.",
                "Click a tile to add the suggestion.",
            )
        )
        grouped_options = group_chip_options_by_label(formatted_options)
        clicked_entry: tuple[str, str] | None = None
        for group_index, (label, group_entries) in enumerate(grouped_options):
            st.caption(label)
            values_only = [value for _group, value in group_entries]
            clicked_index = render_chip_button_grid(
                values_only,
                key_prefix=f"{widget_prefix}.chips.{group_index}",
                columns=3,
            )
            if clicked_index is not None:
                clicked_entry = group_entries[clicked_index]
                break
        st.markdown("</div>", unsafe_allow_html=True)

        if clicked_entry is not None:
            _group, value = clicked_entry
            merged = sorted(
                set(data["requirements"].get(target_key, [])).union([value]),
                key=str.casefold,
            )
            if target_key == "certificates":
                _set_requirement_certificates(data["requirements"], merged)
            else:
                data["requirements"][target_key] = merged
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.rerun()

        if st.button(
            tr("🔄 Vorschläge aktualisieren", "🔄 Refresh suggestions"),
            key=f"{widget_prefix}.refresh",
            width="stretch",
        ):
            st.session_state.pop(StateKeys.SKILL_SUGGESTIONS, None)
            st.rerun()

    responsibilities = data.setdefault("responsibilities", {})
    responsibilities_items = [str(item) for item in responsibilities.get("items", []) if isinstance(item, str)]
    responsibilities_key = "ui.requirements.responsibilities"
    responsibilities_seed_key = f"{responsibilities_key}.__seed"

    responsibilities_label = tr("Kernaufgaben", "Core responsibilities")
    responsibilities_required = "responsibilities.items" in missing_here
    display_label = (
        f"{responsibilities_label}{REQUIRED_SUFFIX}" if responsibilities_required else responsibilities_label
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
        cleaned_responsibilities = render_list_text_area(
            label=display_label,
            session_key=responsibilities_key,
            items=responsibilities_items,
            placeholder=tr(
                "z. B. Produkt-Roadmap planen\nStakeholder-Workshops moderieren",
                "e.g., Plan the product roadmap\nFacilitate stakeholder workshops",
            ),
            height=200,
            required=responsibilities_required,
            on_required=_render_required_caption,
        )
        responsibilities["items"] = cleaned_responsibilities

        lang_code = st.session_state.get("lang", "de")
        last_ai_state = st.session_state.get(StateKeys.RESPONSIBILITY_SUGGESTIONS)
        if isinstance(last_ai_state, Mapping) and last_ai_state.get("_lang") == lang_code:
            status = last_ai_state.get("status")
            if status in {"applied", "empty"}:
                if status == "applied" and last_ai_state.get("items"):
                    st.success(
                        tr(
                            "KI-Aufgaben eingefügt – bitte nach Bedarf feinjustieren.",
                            "AI responsibilities inserted – adjust them as needed.",
                        )
                    )
                    st.markdown("\n".join(f"- {item}" for item in last_ai_state.get("items", [])))
                elif status == "empty":
                    st.info(
                        tr(
                            "Keine neuen Aufgaben gefunden – ergänze mehr Kontext oder formuliere sie manuell.",
                            "No new responsibilities were generated – add more context or enter them manually.",
                        )
                    )
                updated_state = dict(last_ai_state)
                updated_state["status"] = None
                st.session_state[StateKeys.RESPONSIBILITY_SUGGESTIONS] = updated_state

        job_title = str(data.get("position", {}).get("job_title") or "").strip()
        company_name = str(data.get("company", {}).get("name") or "").strip()
        team_structure = str(data.get("position", {}).get("team_structure") or "").strip()
        industry = str(data.get("company", {}).get("industry") or "").strip()
        tone_style = st.session_state.get(UIKeys.TONE_SELECT)

        button_label = "💡 " + tr("Aufgaben vorschlagen", "Suggest responsibilities")
        disabled_reasons: list[str] = []
        if has_missing_key:
            disabled_reasons.append(llm_disabled_message())
        if not job_title:
            disabled_reasons.append(
                tr(
                    "Jobtitel erforderlich, um KI-Vorschläge zu erhalten.",
                    "Add a job title to enable AI suggestions.",
                )
            )

        for reason in disabled_reasons:
            st.caption(reason)

        if st.button(
            button_label,
            key=UIKeys.RESPONSIBILITY_SUGGEST,
            disabled=bool(disabled_reasons),
        ):
            with st.spinner(tr("KI schlägt Aufgaben vor…", "Fetching AI responsibilities…")):
                responsibility_suggestions, suggestion_error = get_responsibility_suggestions(
                    job_title,
                    lang=lang_code,
                    tone_style=tone_style,
                    company_name=company_name,
                    team_structure=team_structure,
                    industry=industry,
                    existing_items=cleaned_responsibilities,
                )
            if suggestion_error:
                st.error(
                    tr(
                        "Aufgaben-Vorschläge fehlgeschlagen: {error}",
                        "Responsibility suggestions failed: {error}",
                    ).format(error=suggestion_error)
                )
                if st.session_state.get("debug"):
                    st.session_state["responsibility_suggest_error"] = suggestion_error
            else:
                if responsibility_suggestions:
                    merged = merge_unique_items(cleaned_responsibilities, responsibility_suggestions)
                    responsibilities["items"] = merged
                    joined = "\n".join(merged)
                    st.session_state[responsibilities_key] = joined
                    st.session_state[responsibilities_seed_key] = joined
                    st.session_state[StateKeys.RESPONSIBILITY_SUGGESTIONS] = {
                        "_lang": lang_code,
                        "items": responsibility_suggestions,
                        "status": "applied",
                    }
                else:
                    st.session_state[StateKeys.RESPONSIBILITY_SUGGESTIONS] = {
                        "_lang": lang_code,
                        "items": [],
                        "status": "empty",
                    }
                st.rerun()

    llm_skill_sources: dict[str, dict[str, list[str]]] = {}
    for pool_key in ("hard_skills", "soft_skills"):
        grouped = suggestions.get(pool_key)
        if not isinstance(grouped, Mapping):
            continue
        normalized_groups: dict[str, list[str]] = {}
        for group_key, values in grouped.items():
            if not isinstance(values, Sequence):
                continue
            cleaned_values = [str(value).strip() for value in values if isinstance(value, str) and str(value).strip()]
            if cleaned_values:
                normalized_groups[str(group_key)] = cleaned_values
        if normalized_groups:
            llm_skill_sources[pool_key] = normalized_groups

    esco_skill_candidates = unique_normalized(
        [
            str(skill).strip()
            for skill in st.session_state.get(StateKeys.ESCO_SKILLS, []) or []
            if isinstance(skill, str) and str(skill).strip()
        ]
    )
    missing_esco_skills = unique_normalized(
        [
            str(skill).strip()
            for skill in st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
            if isinstance(skill, str) and str(skill).strip()
        ]
    )

    _render_skill_board(
        requirements,
        llm_suggestions=llm_skill_sources,
        esco_skills=esco_skill_candidates,
        missing_esco_skills=missing_esco_skills,
    )

    must_col, nice_col = st.columns(2, gap="large")
    tools_col, language_col = st.columns(2, gap="large")

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
        parent=must_col,
    ):
        must_cols = st.columns(2, gap="large")
        label_hard_req = tr("Hard Skills (Pflicht)", "Hard skills (required)")
        if "requirements.hard_skills_required" in missing_here:
            label_hard_req += REQUIRED_SUFFIX
        with must_cols[0]:
            data["requirements"]["hard_skills_required"] = chip_multiselect(
                label_hard_req,
                options=data["requirements"].get("hard_skills_required", []),
                values=data["requirements"].get("hard_skills_required", []),
                help_text=tr(
                    "Zwingend benötigte technische Kompetenzen.",
                    "Essential technical competencies.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_HARD_SKILLS_REQUIRED_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
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
        label_soft_req = tr("Soft Skills (Pflicht)", "Soft skills (required)")
        if "requirements.soft_skills_required" in missing_here:
            label_soft_req += REQUIRED_SUFFIX
        with must_cols[1]:
            data["requirements"]["soft_skills_required"] = chip_multiselect(
                label_soft_req,
                options=data["requirements"].get("soft_skills_required", []),
                values=data["requirements"].get("soft_skills_required", []),
                help_text=tr(
                    "Unverzichtbare Verhalten- und Teamkompetenzen.",
                    "Critical behavioural and team skills.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_SOFT_SKILLS_REQUIRED_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
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
        parent=nice_col,
    ):
        nice_cols = st.columns(2, gap="large")
        with nice_cols[0]:
            data["requirements"]["hard_skills_optional"] = chip_multiselect(
                tr("Hard Skills (Optional)", "Hard skills (optional)"),
                options=data["requirements"].get("hard_skills_optional", []),
                values=data["requirements"].get("hard_skills_optional", []),
                help_text=tr(
                    "Zusätzliche technische Stärken, die Mehrwert bieten.",
                    "Additional technical strengths that add value.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_HARD_SKILLS_OPTIONAL_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
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
            data["requirements"]["soft_skills_optional"] = chip_multiselect(
                tr("Soft Skills (Optional)", "Soft skills (optional)"),
                options=data["requirements"].get("soft_skills_optional", []),
                values=data["requirements"].get("soft_skills_optional", []),
                help_text=tr(
                    "Wünschenswerte persönliche Eigenschaften.",
                    "Valuable personal attributes.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_SOFT_SKILLS_OPTIONAL_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
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
        parent=tools_col,
    ):
        tech_cert_cols = st.columns(2, gap="large")
        with tech_cert_cols[0]:
            data["requirements"]["tools_and_technologies"] = chip_multiselect(
                tr("Tools & Tech", "Tools & Tech"),
                options=data["requirements"].get("tools_and_technologies", []),
                values=data["requirements"].get("tools_and_technologies", []),
                help_text=tr(
                    "Wichtige Systeme, Plattformen oder Sprachen.",
                    "Key systems, platforms, or languages.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_TOOLS_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
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
            selected_certificates = chip_multiselect(
                tr("Zertifikate", "Certificates"),
                options=certificate_options,
                values=certificate_options,
                help_text=tr(
                    "Benötigte Zertifikate oder Nachweise.",
                    "Required certificates or attestations.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_CERTIFICATES_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_CERTIFICATES),
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
        parent=language_col,
    ):
        lang_cols = st.columns(2, gap="large")
        with lang_cols[0]:
            data["requirements"]["languages_required"] = chip_multiselect(
                tr("Sprachen", "Languages"),
                options=data["requirements"].get("languages_required", []),
                values=data["requirements"].get("languages_required", []),
                help_text=tr(
                    "Sprachen, die zwingend erforderlich sind.",
                    "Languages that are mandatory for the role.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_REQUIRED_LANGUAGES_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED),
            )
        with lang_cols[1]:
            data["requirements"]["languages_optional"] = chip_multiselect(
                tr("Optionale Sprachen", "Optional languages"),
                options=data["requirements"].get("languages_optional", []),
                values=data["requirements"].get("languages_optional", []),
                help_text=tr(
                    "Sprachen, die ein Plus darstellen.",
                    "Languages that are a plus.",
                ),
                dropdown=True,
                add_more_hint=ADD_MORE_OPTIONAL_LANGUAGES_HINT,
                state_key=str(ProfilePaths.REQUIREMENTS_LANGUAGES_OPTIONAL),
            )

        current_language_level = data["requirements"].get("language_level_english") or ""
        language_level_options = list(CEFR_LANGUAGE_LEVELS)
        if current_language_level and current_language_level not in language_level_options:
            language_level_options.append(current_language_level)
        selected_level = widget_factory.select(
            "requirements.language_level_english",
            tr("Englischniveau", "English level"),
            language_level_options,
            default=current_language_level,
            format_func=_format_language_level_option,
            help=tr(
                "Wähle das minimale Englischniveau für die Rolle.",
                "Select the minimum English proficiency level for the role.",
            ),
        )
        data["requirements"]["language_level_english"] = selected_level

    with requirement_panel(
        icon="🛡️",
        title=tr("Compliance Checks", "Compliance Checks"),
        caption=tr(
            "Steuert, welche Screenings verpflichtend sind.",
            "Control which screenings are mandatory.",
        ),
        tooltip=tr(
            "Recruiter:innen legen fest, ob Hintergrund-, Referenz- oder Portfolio-Prüfungen nötig sind.",
            "Recruiters decide whether background, reference, or portfolio checks are required.",
        ),
        parent=language_col,
    ):
        _render_compliance_toggle_group(requirements)

    must_insight_skills = (
        list(data["requirements"].get("hard_skills_required", []))
        + list(data["requirements"].get("soft_skills_required", []))
        + list(data["requirements"].get("tools_and_technologies", []))
        + _collect_combined_certificates(data["requirements"])
    )
    nice_insight_skills = list(data["requirements"].get("hard_skills_optional", [])) + list(
        data["requirements"].get("soft_skills_optional", [])
    )
    language_insight_skills = list(data["requirements"].get("languages_required", [])) + list(
        data["requirements"].get("languages_optional", [])
    )
    insight_groups = {
        tr("Muss-Anforderungen", "Must-have requirements"): must_insight_skills,
        tr("Nice-to-have", "Nice-to-have"): nice_insight_skills,
        tr("Sprachen", "Languages"): language_insight_skills,
    }
    insight_groups = {
        label: [skill for skill in skills if isinstance(skill, str) and skill.strip()]
        for label, skills in insight_groups.items()
        if any(isinstance(skill, str) and skill.strip() for skill in skills)
    }

    with requirement_panel(
        icon="📍",
        title=tr("Markt-Insights", "Market insights"),
        caption=tr(
            "Ein konsolidierter Blick auf Gehalts- und Talentwirkung deiner Anforderungen.",
            "A consolidated view on salary and talent impact for your requirements.",
        ),
        tooltip=tr(
            "Passe Radius und Auswahl an, um Benchmarks regional zu fokussieren.",
            "Adjust radius and selection to focus the benchmarks on your region.",
        ),
        variant="insights",
    ):
        radius_default_raw = location_data.get("talent_radius_km", 50)
        try:
            radius_default_int = int(float(radius_default_raw))
        except (TypeError, ValueError):
            radius_default_int = 50
        radius_default_int = min(200, max(10, radius_default_int))
        radius_value = st.slider(
            tr("Standort-Radius", "Location radius"),
            min_value=10,
            max_value=200,
            value=radius_default_int,
            step=5,
            help=tr(
                "Bestimmt, in welchem Umkreis wir Skill-Benchmarks priorisieren (in Kilometern).",
                "Determines the catchment area for prioritising skill benchmarks (in kilometres).",
            ),
        )
        location_data["talent_radius_km"] = int(radius_value)

        location_parts: list[str] = []
        for key in ("primary_city", "region", "state", "province", "country"):
            raw_value = location_data.get(key)
            if not raw_value:
                continue
            cleaned_value = str(raw_value).strip()
            if cleaned_value and cleaned_value not in location_parts:
                location_parts.append(cleaned_value)
        if location_parts:
            region_caption = tr(
                "Region: {region} · Radius {radius} km",
                "Region: {region} · Radius {radius} km",
            ).format(region=", ".join(location_parts), radius=radius_value)
            st.caption(region_caption)
        else:
            st.caption(
                tr(
                    "Trage einen Standort im Unternehmensschritt ein, um regionale Benchmarks zu präzisieren.",
                    "Provide a location in the company step to refine regional benchmarks.",
                )
            )

        render_skill_market_insights(
            insight_groups,
            segment_label=tr("Ausgewählte Anforderungen", "Selected requirements"),
            empty_message=tr(
                "Noch keine Anforderungen hinterlegt – ergänze Skills oder Sprachen für Markt-Insights.",
                "No requirements captured yet – add skills or languages to unlock market insights.",
            ),
            location=location_data,
            radius_km=float(radius_value),
        )

    # Inline follow-up questions for Requirements & Responsibilities
    _render_followups_for_step("role_tasks", data)


def _update_section_progress(
    missing_fields: Iterable[str] | None = None,
) -> tuple[int | None, list[int]]:
    """Update session state with completion information for wizard sections."""

    fields = list(missing_fields) if missing_fields is not None else get_missing_critical_fields()
    fields = list(dict.fromkeys(fields))
    sections_with_missing = {resolve_section_for_field(field) for field in fields}

    first_incomplete: int | None = None
    for section in CRITICAL_SECTION_ORDER:
        if section in sections_with_missing:
            first_incomplete = section
            break

    if first_incomplete is None and sections_with_missing:
        first_incomplete = resolve_section_for_field(next(iter(fields)))

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


def _step_compensation() -> None:
    """Render the compensation and benefits step.

    Returns:
        None
    """

    profile = _get_profile_state()
    title, subtitle, intros = _resolve_step_copy("benefits", profile)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)
    lang = st.session_state.get("lang", "de")
    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    job_title = str(position.get("job_title") or "").strip()
    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    country_raw = str(location.get("country") or "").strip()
    iso_country = country_to_iso2(country_raw) if country_raw else ""
    city = _profile_city(profile) or ""
    local_context = (job_title, iso_country, city)
    stored_local_context = st.session_state.get(StateKeys.LOCAL_BENEFIT_CONTEXT)
    if stored_local_context != local_context:
        st.session_state[StateKeys.LOCAL_BENEFIT_CONTEXT] = local_context
        st.session_state[StateKeys.LOCAL_BENEFIT_SUGGESTIONS] = []

    data = profile

    slider_defaults = _derive_salary_range_defaults(profile)
    inject_salary_slider_styles()
    slider_label = tr("Gehaltsspanne (Brutto)", "Salary range (gross)", lang=lang)
    slider_help = tr(
        "Bruttojahresband per Schieberegler anpassen.",
        "Adjust the gross annual range with the slider.",
        lang=lang,
    )
    salary_min, salary_max = st.slider(
        slider_label,
        min_value=SALARY_SLIDER_MIN,
        max_value=SALARY_SLIDER_MAX,
        value=(slider_defaults.minimum, slider_defaults.maximum),
        step=SALARY_SLIDER_STEP,
        help=slider_help,
        key="ui.compensation.salary_range",
    )
    data["compensation"]["salary_min"] = int(salary_min)
    data["compensation"]["salary_max"] = int(salary_max)
    data["compensation"]["salary_provided"] = bool(salary_min or salary_max)

    current_currency = data["compensation"].get("currency")
    if not current_currency and slider_defaults.currency:
        data["compensation"]["currency"] = slider_defaults.currency
        current_currency = slider_defaults.currency

    details_label = tr(
        "Währungs- & Periodendetails",
        "Currency & period details",
        lang=lang,
    )
    with st.expander(details_label, expanded=False):
        c1, c2 = st.columns(2)
        currency_options = ["EUR", "USD", "CHF", "GBP", "Other"]
        current_currency = data["compensation"].get("currency") or "EUR"
        currency_index = (
            currency_options.index(current_currency)
            if current_currency in currency_options
            else currency_options.index("Other")
        )
        currency_label = tr("Währung", "Currency", lang=lang)
        selected_currency = c1.selectbox(
            currency_label,
            options=currency_options,
            index=currency_index,
        )
        if selected_currency == "Other":
            other_currency = c1.text_input(
                tr("Andere Währung", "Other currency", lang=lang),
                value=("" if current_currency in currency_options else str(current_currency)),
            )
            data["compensation"]["currency"] = other_currency.strip()
        else:
            data["compensation"]["currency"] = selected_currency

        period_options = ["year", "month", "day", "hour"]
        current_period = data["compensation"].get("period")
        period_index = period_options.index(current_period) if current_period in period_options else 0
        data["compensation"]["period"] = c2.selectbox(
            tr("Periode", "Period", lang=lang),
            options=period_options,
            index=period_index,
        )

    toggle_variable, toggle_equity = st.columns(2)
    data["compensation"]["variable_pay"] = toggle_variable.toggle(
        tr("Variable Vergütung?", "Variable pay?", lang=lang),
        value=bool(data["compensation"].get("variable_pay")),
    )
    data["compensation"]["equity_offered"] = toggle_equity.toggle(
        tr("Mitarbeiterbeteiligung?", "Equity?", lang=lang),
        value=bool(data["compensation"].get("equity_offered")),
    )

    if data["compensation"]["variable_pay"]:
        c4, c5 = st.columns(2)
        data["compensation"]["bonus_percentage"] = c4.number_input(
            tr("Bonus %", "Bonus %", lang=lang),
            min_value=0.0,
            max_value=100.0,
            value=float(data["compensation"].get("bonus_percentage") or 0.0),
        )
        data["compensation"]["commission_structure"] = c5.text_input(
            tr("Provisionsmodell", "Commission structure", lang=lang),
            value=data["compensation"].get("commission_structure", ""),
        )

    benefit_focus_presets = _BENEFIT_FOCUS_PRESETS.get(lang, _BENEFIT_FOCUS_PRESETS["en"])
    industry_context = data.get("company", {}).get("industry", "")
    fallback_benefits = get_static_benefit_shortlist(lang=lang, industry=industry_context)
    benefit_state = st.session_state.get(StateKeys.BENEFIT_SUGGESTIONS, {})
    if benefit_state.get("_lang") != lang:
        benefit_state = {"llm": [], "fallback": fallback_benefits, "_lang": lang}
    else:
        benefit_state.setdefault("fallback", fallback_benefits)
    llm_benefits = unique_normalized(str(item) for item in benefit_state.get("llm", []))
    fallback_pool = unique_normalized(str(item) for item in benefit_state.get("fallback", fallback_benefits))
    benefit_state["llm"] = llm_benefits
    benefit_state["fallback"] = fallback_pool
    st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = benefit_state

    suggestion_bundle = resolve_sidebar_benefits(lang=lang, industry=industry_context)
    llm_benefits = list(suggestion_bundle.llm_suggestions)
    fallback_pool = list(suggestion_bundle.fallback_suggestions)
    existing_benefits = unique_normalized(str(item) for item in data["compensation"].get("benefits", []))
    combined_options = merge_unique_items(existing_benefits, fallback_pool)
    combined_options = merge_unique_items(combined_options, llm_benefits)
    benefit_options = sorted(combined_options, key=str.casefold)
    selected_benefits = chip_multiselect(
        tr("Leistungen", "Benefits", lang=lang),
        options=benefit_options,
        values=existing_benefits,
        add_more_hint=ADD_MORE_BENEFITS_HINT,
        state_key=str(ProfilePaths.COMPENSATION_BENEFITS),
    )
    data["compensation"]["benefits"] = unique_normalized(selected_benefits)

    stored_benefit_focus = st.session_state.get(StateKeys.BENEFIT_SUGGESTION_HINTS, [])
    benefit_focus_options = sorted(
        {value.strip() for value in benefit_focus_presets if value.strip()}.union(
            {value.strip() for value in stored_benefit_focus if value.strip()}
        ),
        key=str.casefold,
    )
    selected_benefit_focus = chip_multiselect(
        tr(
            "Fokus für Benefit-Vorschläge",
            "Focus for AI benefit suggestions",
            lang=lang,
        ),
        options=benefit_focus_options,
        values=stored_benefit_focus,
        help_text=tr(
            "Lege Kategorien fest, auf die die KI ihre Benefit-Vorschläge ausrichten soll.",
            "Define categories the AI should emphasise when proposing benefits.",
            lang=lang,
        ),
        dropdown=True,
        add_more_hint=ADD_MORE_BENEFIT_FOCUS_HINT,
        state_key=StateKeys.BENEFIT_SUGGESTION_HINTS,
    )
    st.session_state[StateKeys.BENEFIT_SUGGESTION_HINTS] = selected_benefit_focus

    show_benefit_section = bool(suggestion_bundle.suggestions)
    if show_benefit_section:
        render_section_heading(
            tr("Benefit-Ideen", "Benefit ideas", lang=lang),
            icon="🎁",
            size="compact",
        )
        st.caption(
            tr(
                "Inspiration aus den letzten Vorschlägen.",
                "Inspiration based on the latest suggestions.",
                lang=lang,
            )
        )
        if suggestion_bundle.source == "fallback" and not suggestion_bundle.llm_suggestions:
            st.caption(
                tr(
                    "Keine KI-Vorschläge verfügbar – zeige Standardliste.",
                    "No AI suggestions available – showing fallback shortlist.",
                    lang=lang,
                )
            )

    suggestion_entries: list[tuple[str, str, str]] = []
    existing_benefit_markers = {str(item).casefold() for item in data["compensation"].get("benefits", []) or []}
    seen_benefit_options: set[tuple[str, str]] = set()
    for group_key, label in (
        ("llm", tr("LLM-Vorschläge", "LLM suggestions", lang=lang)),
        ("fallback", tr("Standardliste", "Fallback shortlist", lang=lang)),
    ):
        pool = llm_benefits if group_key == "llm" else fallback_pool
        for raw in pool:
            benefit = str(raw or "").strip()
            if not benefit:
                continue
            marker = benefit.casefold()
            marker_key = (group_key, marker)
            if marker in existing_benefit_markers or marker_key in seen_benefit_options:
                continue
            seen_benefit_options.add(marker_key)
            suggestion_entries.append((group_key, benefit, label))

    if suggestion_entries:
        suggestion_key = "benefit_suggestions.selection"
        formatted_benefits = sorted(
            suggestion_entries,
            key=lambda item: (0 if item[0] == "llm" else 1, item[1].casefold()),
        )
        suggestion_label = tr(
            "Vorschläge aus KI & Liste",
            "Suggestions from AI & shortlist",
            lang=lang,
        )
        st.markdown(f"**{suggestion_label}**")
        st.caption(
            tr(
                "Klicke auf eine Box, um den Vorschlag zu übernehmen.",
                "Click a tile to add the suggestion.",
                lang=lang,
            )
        )
        grouped_benefits = group_chip_options_by_label(formatted_benefits)
        clicked_entry: tuple[str, str] | None = None
        for group_index, (label, group_entries) in enumerate(grouped_benefits):
            st.caption(label)
            display_values = [value for _group, value in group_entries]
            clicked_index = render_chip_button_grid(
                display_values,
                key_prefix=f"{suggestion_key}.{group_index}",
                columns=3,
            )
            if clicked_index is not None:
                clicked_entry = group_entries[clicked_index]
                break
        if clicked_entry is not None:
            _group, value = clicked_entry
            current_benefits = list(data["compensation"].get("benefits", []))
            merged = sorted(
                merge_unique_items(current_benefits, [value]),
                key=str.casefold,
            )
            data["compensation"]["benefits"] = merged
            st.rerun()
    elif show_benefit_section:
        st.caption(
            tr(
                "Alle vorgeschlagenen Benefits wurden bereits übernommen.",
                "All suggested benefits are already part of your list.",
                lang=lang,
            )
        )

    llm_available = is_llm_available()
    if not llm_available:
        st.caption(llm_disabled_message(lang=lang))
    if st.button(
        "💡 " + tr("Benefits vorschlagen", "Suggest Benefits", lang=lang),
        disabled=not llm_available,
    ):
        job_title = data.get("position", {}).get("job_title", "")
        industry = data.get("company", {}).get("industry", "")
        existing = "\n".join(data["compensation"].get("benefits", []))
        local_benefits = _generate_local_benefits(profile, lang=lang)
        st.session_state[StateKeys.LOCAL_BENEFIT_SUGGESTIONS] = local_benefits
        spinner_label = tr(
            "Generiere Benefit-Vorschläge…",
            "Generating benefit suggestions…",
            lang=lang,
        )
        with st.spinner(spinner_label):
            new_sugg, err, used_fallback = get_benefit_suggestions(
                job_title,
                industry,
                existing,
                lang=lang,
                focus_areas=selected_benefit_focus,
                tone_style=st.session_state.get(UIKeys.TONE_SELECT),
            )
        if used_fallback:
            st.info(
                tr(
                    "Keine KI-Vorschläge verfügbar – zeige Standardliste.",
                    "No AI suggestions available – showing fallback list.",
                    lang=lang,
                )
            )
        elif err:
            st.warning(
                tr(
                    "Benefit-Vorschläge nicht verfügbar (API-Fehler)",
                    "Benefit suggestions not available (API error)",
                    lang=lang,
                )
            )
        if err and st.session_state.get("debug"):
            st.session_state["benefit_suggest_error"] = err
        if new_sugg:
            benefit_state = st.session_state.get(
                StateKeys.BENEFIT_SUGGESTIONS,
                {"llm": [], "fallback": fallback_benefits, "_lang": lang},
            )
            benefit_state["_lang"] = lang
            if used_fallback:
                benefit_state["llm"] = []
                benefit_state["fallback"] = unique_normalized(str(item) for item in new_sugg)
            else:
                benefit_state["llm"] = unique_normalized(str(item) for item in new_sugg)
                benefit_state["fallback"] = fallback_pool
            st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = benefit_state
            st.rerun()

    local_suggestions = st.session_state.get(StateKeys.LOCAL_BENEFIT_SUGGESTIONS, [])
    if local_suggestions:
        st.markdown(f"**{tr('Lokale Benefit-Ideen', 'Local benefit ideas', lang=lang)}**")
        st.caption(
            tr(
                "Regional passende Zusatzleistungen zur Inspiration.",
                "Regionally flavoured benefits for inspiration.",
                lang=lang,
            )
        )
        for benefit in local_suggestions:
            st.markdown(f"- {benefit}")

    # Inline follow-up questions for Compensation section
    _render_followups_for_step("benefits", data)


def _step_process() -> None:
    """Render the hiring process step."""

    profile = _get_profile_state()
    title, subtitle, intros = _resolve_step_copy("interview", profile)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)
    data = profile["process"]

    stakeholders_raw = data.get("stakeholders")
    stakeholders_list = stakeholders_raw if isinstance(stakeholders_raw, list) else []
    has_stakeholder_details = any(
        any(str(person.get(field) or "").strip() for field in ("name", "role", "email"))
        or bool(person.get("information_loop_phases"))
        for person in stakeholders_list
        if isinstance(person, Mapping)
    )
    if not has_stakeholder_details:
        st.info(
            tr(
                (
                    "Erfasse hier deinen Ansprechpartner, damit in der Übersicht nicht der Hinweis "
                    "„Keine Stakeholder hinterlegt – Schritt 'Prozess' ausfüllen, um Personen zu ergänzen.“"
                    " erscheint."
                ),
                (
                    "Capture your primary contact here so the summary doesn’t display the hint "
                    "“No stakeholders available – populate the Process step to add contacts.”."
                ),
            )
        )

    hiring_cols = st.columns(2)
    data["hiring_manager_name"] = hiring_cols[0].text_input(
        tr("Hiring Manager", "Hiring manager"),
        value=data.get("hiring_manager_name", ""),
    )
    data["hiring_manager_role"] = hiring_cols[1].text_input(
        tr("Rolle des Hiring Managers", "Hiring manager role"),
        value=data.get("hiring_manager_role", ""),
    )
    _update_profile("process.hiring_manager_name", data.get("hiring_manager_name", ""))
    _update_profile("process.hiring_manager_role", data.get("hiring_manager_role", ""))

    _render_stakeholders(data, "ui.process.stakeholders")
    _render_phases(data, data.get("stakeholders", []), "ui.process.phases")

    render_section_heading(
        tr("Interne Prozesse definieren", "Define internal processes"),
        icon="🧭",
    )
    st.caption(
        tr(
            "Ordne Informationsschleifen zu und halte Aufgaben für jede Phase fest.",
            "Assign information loops and capture tasks for each process phase.",
        )
    )

    stakeholders_preview = data.get("stakeholders", []) or []
    phases_preview = data.get("phases", []) or []

    process_cols = st.columns(2, gap="small")
    with process_cols[0]:
        render_section_heading(tr("Informationsschleifen", "Information loops"), size="compact")
        phase_labels = _phase_display_labels(phases_preview)
        phase_indices = list(range(len(phase_labels)))
        if not stakeholders_preview:
            st.info(
                tr(
                    "Keine Stakeholder hinterlegt – Schritt 'Prozess' ausfüllen, um Personen zu ergänzen.",
                    "No stakeholders available – populate the Process step to add contacts.",
                )
            )
        else:
            for idx, person in enumerate(stakeholders_preview):
                display_name = person.get("name") or tr("Stakeholder {number}", "Stakeholder {number}").format(
                    number=idx + 1
                )
                st.markdown(f"**{display_name}**")
                existing_selection = _filter_phase_indices(
                    person.get("information_loop_phases", []), len(phase_indices)
                )
                if existing_selection != person.get("information_loop_phases"):
                    person["information_loop_phases"] = existing_selection
                if phase_indices:
                    label_pairs = [(str(index), _phase_label_formatter(phase_labels)(index)) for index in phase_indices]
                    selected_phase_strings = [str(index) for index in existing_selection]
                    chosen_phases = chip_multiselect_mapped(
                        tr("Phasen", "Phases"),
                        option_pairs=label_pairs,
                        values=selected_phase_strings,
                        dropdown=True,
                        state_key=f"process.information_loops.{idx}",
                        add_more_hint=ADD_MORE_PHASES_HINT,
                    )
                    person["information_loop_phases"] = [int(value) for value in chosen_phases if str(value).isdigit()]
                else:
                    person["information_loop_phases"] = []
            if not phase_indices:
                st.info(
                    tr(
                        "Lege Prozessphasen an, um Informationsschleifen zuzuweisen.",
                        "Create process phases to assign information loops.",
                    )
                )

    with process_cols[1]:
        render_section_heading(tr("Aufgaben & Übergaben", "Tasks & handovers"), size="compact")
        if not phases_preview:
            st.info(
                tr(
                    "Noch keine Phasen definiert – Schritt 'Prozess' ergänzt Aufgaben.",
                    "No phases defined yet – use the Process step to add them.",
                )
            )
        else:
            for idx, phase in enumerate(phases_preview):
                phase_name = phase.get("name") or tr("Phase {number}", "Phase {number}").format(number=idx + 1)
                st.markdown(f"**{phase_name}**")
                current_tasks = phase.get("task_assignments", "")
                phase["task_assignments"] = st.text_area(
                    tr("Aufgabenbeschreibung", "Task notes"),
                    value=current_tasks,
                    key=f"process.tasks.{idx}",
                    label_visibility="collapsed",
                    placeholder=tr(
                        "To-dos, Verantwortlichkeiten und Hand-offs …",
                        "To-dos, responsibilities, and hand-offs …",
                    ),
                )

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
    if original_timeline and not _parse_timeline_range(str(original_timeline))[0] and not changed:
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
    _render_followups_for_step("interview", profile)


_MAX_SECTION_INDEX = max(CRITICAL_SECTION_ORDER or (COMPANY_STEP_INDEX,))


def _summary_company() -> None:
    """Editable summary tab for company information."""

    data = _get_profile_state()
    c1, c2 = st.columns(2)
    summary_company_label = tr(*COMPANY_NAME_LABEL) + REQUIRED_SUFFIX
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
        tr("Hauptsitz (Stadt, Land)", "Headquarters (city, country)"),
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
    company_brand_value = data["company"].get("brand_keywords", "")
    company_brand_default = company_brand_value if isinstance(company_brand_value, str) else ""
    if UIKeys.COMPANY_BRAND_KEYWORDS not in st.session_state:
        st.session_state[UIKeys.COMPANY_BRAND_KEYWORDS] = company_brand_default

    if st.session_state.pop(UIKeys.JOB_AD_BRAND_TONE_SYNC_FLAG, False):
        synced_brand = st.session_state.get(UIKeys.JOB_AD_BRAND_TONE)
        st.session_state[UIKeys.COMPANY_BRAND_KEYWORDS] = synced_brand if isinstance(synced_brand, str) else ""

    brand = st.text_input(
        tr("Brand-Ton oder Keywords", "Brand tone or keywords"),
        value=st.session_state.get(UIKeys.COMPANY_BRAND_KEYWORDS, ""),
        key=UIKeys.COMPANY_BRAND_KEYWORDS,
    )
    contact_cols = st.columns((1.2, 1.2, 1))
    contact_name = contact_cols[0].text_input(
        tr(*COMPANY_CONTACT_NAME_LABEL),
        value=data["company"].get("contact_name", ""),
        key="ui.summary.company.contact_name",
    )
    contact_email = contact_cols[1].text_input(
        tr(*COMPANY_CONTACT_EMAIL_LABEL),
        value=data["company"].get("contact_email", ""),
        key="ui.summary.company.contact_email",
    )
    contact_phone = contact_cols[2].text_input(
        tr(*COMPANY_CONTACT_PHONE_LABEL),
        value=data["company"].get("contact_phone", ""),
        key="ui.summary.company.contact_phone",
    )
    logo_bytes = _get_company_logo_bytes()
    if logo_bytes:
        try:
            st.image(logo_bytes, width=120)
        except Exception:
            st.caption(tr("Logo erfolgreich geladen.", "Logo uploaded successfully."))

    _update_profile(ProfilePaths.COMPANY_NAME, name)
    _update_profile(ProfilePaths.COMPANY_INDUSTRY, industry)
    _update_profile(ProfilePaths.COMPANY_HQ_LOCATION, hq)
    _update_profile(ProfilePaths.COMPANY_SIZE, size)
    _update_profile(ProfilePaths.COMPANY_WEBSITE, website)
    _update_profile(ProfilePaths.COMPANY_MISSION, mission)
    _update_profile(ProfilePaths.COMPANY_CULTURE, culture)
    _update_profile(ProfilePaths.COMPANY_BRAND_KEYWORDS, brand)
    _update_profile(ProfilePaths.COMPANY_CONTACT_NAME, contact_name)
    _update_profile(ProfilePaths.COMPANY_CONTACT_EMAIL, contact_email)
    _update_profile(ProfilePaths.COMPANY_CONTACT_PHONE, contact_phone)


def _summary_position() -> None:
    """Editable summary tab for position details."""

    profile_state = st.session_state.get(StateKeys.PROFILE)
    summary_data: dict[str, Any] = {}
    if isinstance(profile_state, dict):
        summary_data = profile_state
    elif isinstance(profile_state, Mapping):
        summary_data = dict(profile_state)
        st.session_state[StateKeys.PROFILE] = summary_data
    else:
        ensure_state()
        refreshed = st.session_state.get(StateKeys.PROFILE)
        summary_data = refreshed if isinstance(refreshed, dict) else {}
    data = summary_data
    position = data.setdefault("position", {})
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
    team_structure = c2.text_input(
        tr("Teamstruktur", "Team structure"),
        value=data["position"].get("team_structure", ""),
        key="ui.summary.position.team_structure",
    )

    department_data = data.setdefault("department", {})
    team_data = data.setdefault("team", {})

    dept_cols = st.columns(2)
    department_name = dept_cols[0].text_input(
        tr("Abteilung", "Department"),
        value=department_data.get("name", ""),
        key=ProfilePaths.DEPARTMENT_NAME,
    )
    department_function = dept_cols[1].text_input(
        tr("Funktion", "Function"),
        value=department_data.get("function", ""),
        key=ProfilePaths.DEPARTMENT_FUNCTION,
    )

    leader_cols = st.columns(2)
    department_leader_name = leader_cols[0].text_input(
        tr("Abteilungsleitung", "Department lead"),
        value=department_data.get("leader_name", ""),
        key=ProfilePaths.DEPARTMENT_LEADER_NAME,
    )
    department_leader_title = leader_cols[1].text_input(
        tr("Titel der Leitung", "Lead title"),
        value=department_data.get("leader_title", ""),
        key=ProfilePaths.DEPARTMENT_LEADER_TITLE,
    )

    strategic_goals = st.text_area(
        tr("Strategische Ziele", "Strategic goals"),
        value=department_data.get("strategic_goals", ""),
        key=ProfilePaths.DEPARTMENT_STRATEGIC_GOALS,
        height=80,
    )

    team_cols = st.columns(2)
    team_name = team_cols[0].text_input(
        tr("Teamname", "Team name"),
        value=team_data.get("name", ""),
        key=ProfilePaths.TEAM_NAME,
    )
    team_mission = team_cols[1].text_input(
        tr("Teamauftrag", "Team mission"),
        value=team_data.get("mission", ""),
        key=ProfilePaths.TEAM_MISSION,
    )

    reporting_cols = st.columns(2)
    team_reporting = reporting_cols[0].text_input(
        tr("Berichtslinie", "Reporting line"),
        value=team_data.get("reporting_line", data["position"].get("reporting_line", "")),
        key=ProfilePaths.TEAM_REPORTING_LINE,
    )
    reporting_manager_summary_key = UIKeys.SUMMARY_POSITION_REPORTING_MANAGER_NAME
    reporting_manager_contact_key = UIKeys.CONTACT_POSITION_REPORTING_MANAGER_NAME
    default_reporting_manager: str = data["position"].get("reporting_manager_name", "")

    def _sync_reporting_manager_to_contact() -> None:
        """Keep the contact widget aligned with the summary value."""

        st.session_state[reporting_manager_contact_key] = st.session_state.get(
            reporting_manager_summary_key,
            default_reporting_manager,
        )

    def _sync_reporting_manager_to_summary() -> None:
        """Mirror the contact widget value back to the summary input."""

        st.session_state[reporting_manager_summary_key] = st.session_state.get(
            reporting_manager_contact_key,
            default_reporting_manager,
        )

    reporting_manager = reporting_cols[1].text_input(
        tr("Vorgesetzte Person", "Reporting manager"),
        value=default_reporting_manager,
        key=reporting_manager_summary_key,
        on_change=_sync_reporting_manager_to_contact,
    )

    headcount_cols = st.columns(2)
    team_headcount_current = headcount_cols[0].number_input(
        tr("Headcount aktuell", "Current headcount"),
        min_value=0,
        step=1,
        value=int(team_data.get("headcount_current") or 0),
        key=ProfilePaths.TEAM_HEADCOUNT_CURRENT,
    )
    team_headcount_target = headcount_cols[1].number_input(
        tr("Headcount Ziel", "Target headcount"),
        min_value=0,
        step=1,
        value=int(team_data.get("headcount_target") or 0),
        key=ProfilePaths.TEAM_HEADCOUNT_TARGET,
    )

    team_details_cols = st.columns(2)
    team_tools = team_details_cols[0].text_input(
        tr("Tools", "Collaboration tools"),
        value=team_data.get("collaboration_tools", ""),
        key=ProfilePaths.TEAM_COLLABORATION_TOOLS,
    )
    team_locations = team_details_cols[1].text_input(
        tr("Team-Standorte", "Team locations"),
        value=team_data.get("locations", ""),
        key=ProfilePaths.TEAM_LOCATIONS,
    )

    contact_cols = st.columns(2)
    reporting_manager = contact_cols[0].text_input(
        tr("Vorgesetzte Person", "Reporting manager"),
        value=reporting_manager,
        key=reporting_manager_contact_key,
        on_change=_sync_reporting_manager_to_summary,
    )
    customer_contact_required = contact_cols[1].toggle(
        tr(*CUSTOMER_CONTACT_TOGGLE_LABEL),
        value=bool(data["position"].get("customer_contact_required")),
        key=ProfilePaths.POSITION_CUSTOMER_CONTACT_REQUIRED,
        help=tr(*POSITION_CUSTOMER_CONTACT_TOGGLE_HELP),
    )

    if customer_contact_required:
        customer_contact_details = st.text_area(
            tr("Kontakt-Details", "Contact details"),
            value=data["position"].get("customer_contact_details", ""),
            key=ProfilePaths.POSITION_CUSTOMER_CONTACT_DETAILS,
            height=80,
            placeholder=tr(*POSITION_CUSTOMER_CONTACT_DETAILS_HINT),
        )
    else:
        customer_contact_details = ""

    department_data["name"] = department_name
    department_data["function"] = department_function
    department_data["leader_name"] = department_leader_name
    department_data["leader_title"] = department_leader_title
    department_data["strategic_goals"] = strategic_goals
    team_data["name"] = team_name
    team_data["mission"] = team_mission
    team_data["reporting_line"] = team_reporting
    team_data["headcount_current"] = int(team_headcount_current)
    team_data["headcount_target"] = int(team_headcount_target)
    team_data["collaboration_tools"] = team_tools
    team_data["locations"] = team_locations
    position["customer_contact_required"] = customer_contact_required
    if customer_contact_details:
        position["customer_contact_details"] = customer_contact_details
    else:
        position.pop("customer_contact_details", None)
    role_summary = st.text_area(
        tr(*ROLE_SUMMARY_LABEL) + REQUIRED_SUFFIX,
        value=data["position"].get("role_summary", ""),
        height=120,
        key="ui.summary.position.role_summary",
        help=tr("Dieses Feld ist erforderlich", "This field is required"),
    )
    summary_city_lock = _field_lock_config(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        tr(*PRIMARY_CITY_LABEL),
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
        ProfilePaths.LOCATION_COUNTRY,
        tr(*PRIMARY_COUNTRY_LABEL),
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

    _update_profile(ProfilePaths.POSITION_JOB_TITLE, job_title)
    _update_profile(ProfilePaths.POSITION_SENIORITY, seniority)
    _update_profile(ProfilePaths.POSITION_TEAM_STRUCTURE, team_structure)
    _update_profile(ProfilePaths.DEPARTMENT_NAME, department_name)
    _update_profile(ProfilePaths.DEPARTMENT_FUNCTION, department_function)
    _update_profile(ProfilePaths.DEPARTMENT_LEADER_NAME, department_leader_name)
    _update_profile(ProfilePaths.DEPARTMENT_LEADER_TITLE, department_leader_title)
    _update_profile(ProfilePaths.DEPARTMENT_STRATEGIC_GOALS, strategic_goals)
    _update_profile(ProfilePaths.TEAM_NAME, team_name)
    _update_profile(ProfilePaths.TEAM_MISSION, team_mission)
    _update_profile(ProfilePaths.TEAM_REPORTING_LINE, team_reporting)
    _update_profile(ProfilePaths.POSITION_REPORTING_LINE, team_reporting)
    _update_profile(ProfilePaths.TEAM_HEADCOUNT_CURRENT, team_headcount_current)
    _update_profile(ProfilePaths.TEAM_HEADCOUNT_TARGET, team_headcount_target)
    _update_profile(ProfilePaths.TEAM_COLLABORATION_TOOLS, team_tools)
    _update_profile(ProfilePaths.TEAM_LOCATIONS, team_locations)
    _update_profile(ProfilePaths.POSITION_REPORTING_MANAGER_NAME, reporting_manager)
    _update_profile(ProfilePaths.POSITION_CUSTOMER_CONTACT_REQUIRED, customer_contact_required)
    _update_profile(ProfilePaths.POSITION_CUSTOMER_CONTACT_DETAILS, customer_contact_details)
    _update_profile(ProfilePaths.POSITION_ROLE_SUMMARY, role_summary)
    _update_profile(ProfilePaths.LOCATION_PRIMARY_CITY, loc_city)
    _update_profile(ProfilePaths.LOCATION_COUNTRY, loc_country)


def _summary_requirements() -> None:
    """Editable summary tab for requirements."""

    profile_state = st.session_state.get(StateKeys.PROFILE)
    summary_data: dict[str, Any] = {}
    if isinstance(profile_state, dict):
        summary_data = profile_state
    elif isinstance(profile_state, Mapping):
        summary_data = dict(profile_state)
        st.session_state[StateKeys.PROFILE] = summary_data
    else:
        ensure_state()
        refreshed = st.session_state.get(StateKeys.PROFILE)
        summary_data = refreshed if isinstance(refreshed, dict) else {}
    data = summary_data
    requirements: dict[str, Any] = data.setdefault("requirements", {})
    missing_esco = [
        str(skill).strip()
        for skill in st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
        if isinstance(skill, str) and str(skill).strip()
    ]
    if missing_esco:
        outstanding = ", ".join(unique_normalized(missing_esco[:8]))
        st.info(
            tr(
                "Noch ausstehende ESCO-Pflichtskills: {skills}",
                "Outstanding ESCO essentials: {skills}",
            ).format(skills=outstanding)
        )

    hard_req = st.text_area(
        tr("Hard Skills (Pflicht)", "Hard skills (required)"),
        value=", ".join(data["requirements"].get("hard_skills_required", [])),
        key="ui.summary.requirements.hard_skills_required",
    )
    hard_opt = st.text_area(
        tr("Hard Skills (Optional)", "Hard skills (optional)"),
        value=", ".join(data["requirements"].get("hard_skills_optional", [])),
        key="ui.summary.requirements.hard_skills_optional",
    )
    soft_req = st.text_area(
        tr("Soft Skills (Pflicht)", "Soft skills (required)"),
        value=", ".join(data["requirements"].get("soft_skills_required", [])),
        key="ui.summary.requirements.soft_skills_required",
    )
    soft_opt = st.text_area(
        tr("Soft Skills (Optional)", "Soft skills (optional)"),
        value=", ".join(data["requirements"].get("soft_skills_optional", [])),
        key="ui.summary.requirements.soft_skills_optional",
    )
    tools = st.text_area(
        tr("Tools & Tech", "Tools & Tech"),
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

    _render_compliance_toggle_group(requirements)

    st.caption(
        tr(
            "Diese Compliance-Schalter spiegeln den Schritt „Skills & Requirements“ wider – Änderungen aktualisieren beide Ansichten und alle Exporte.",
            "These compliance toggles mirror the “Skills & Requirements” step – updates keep both views and all exports aligned.",
        )
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

    profile_state = st.session_state.get(StateKeys.PROFILE)
    summary_data: dict[str, Any] = {}
    if isinstance(profile_state, dict):
        summary_data = profile_state
    elif isinstance(profile_state, Mapping):
        summary_data = dict(profile_state)
        st.session_state[StateKeys.PROFILE] = summary_data
    else:
        ensure_state()
        refreshed = st.session_state.get(StateKeys.PROFILE)
        summary_data = refreshed if isinstance(refreshed, dict) else {}
    data = summary_data
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
        tr("Arbeitsmodell", "Work policy"),
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
    stored_schedule = str(data["employment"].get("work_schedule") or "").strip()
    custom_schedule_value = ""
    if stored_schedule and stored_schedule not in schedule_options:
        custom_schedule_value = stored_schedule
        schedule_default = "other"
    else:
        schedule_default = stored_schedule or "standard"
    schedule_keys = list(schedule_options.keys())
    schedule_index = schedule_keys.index(schedule_default) if schedule_default in schedule_keys else 0
    schedule_selection = c4.selectbox(
        tr("Arbeitszeitmodell", "Work schedule"),
        options=schedule_keys,
        format_func=lambda x: schedule_options[x],
        index=schedule_index,
        key="ui.summary.employment.work_schedule",
    )
    if schedule_selection == "other":
        work_schedule = c4.text_input(
            tr("Individuelles Modell", "Custom schedule"),
            value=custom_schedule_value,
            placeholder=tr(
                "Arbeitszeitmodell beschreiben",
                "Describe the working time model",
            ),
            key="ui.summary.employment.work_schedule_other",
        ).strip()
    else:
        work_schedule = schedule_selection

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
        default_end = date.fromisoformat(contract_end_str) if contract_end_str else date.today()
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
        travel_details = text_input_with_state(
            tr("Reisedetails", "Travel details"),
            target=data["employment"],
            field="travel_details",
            key="ui.summary.employment.travel_details",
        )
    else:
        travel_details = None

    if relocation:
        relocation_details = text_input_with_state(
            tr("Umzugsunterstützung", "Relocation details"),
            target=data["employment"],
            field="relocation_details",
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
    preset_options = unique_normalized(preset_benefits.get(lang, []))
    existing_benefits = unique_normalized(str(item) for item in data["compensation"].get("benefits", []))
    benefit_options = sorted(
        unique_normalized(existing_benefits + preset_options),
        key=str.casefold,
    )
    benefits = chip_multiselect(
        tr("Leistungen", "Benefits"),
        options=benefit_options,
        values=existing_benefits,
        add_more_hint=ADD_MORE_BENEFITS_HINT,
        state_key=str(ProfilePaths.COMPENSATION_BENEFITS),
    )
    benefits = unique_normalized(benefits)

    _update_profile("compensation.salary_min", salary_min)
    _update_profile("compensation.salary_max", salary_max)
    _update_profile("compensation.salary_provided", bool(salary_min or salary_max))
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

    hiring_cols = st.columns(2)
    hiring_manager = hiring_cols[0].text_input(
        tr("Hiring Manager", "Hiring manager"),
        value=process.get("hiring_manager_name", ""),
        key="ui.summary.process.hiring_manager_name",
    )
    hiring_role = hiring_cols[1].text_input(
        tr("Rolle des Hiring Managers", "Hiring manager role"),
        value=process.get("hiring_manager_role", ""),
        key="ui.summary.process.hiring_manager_role",
    )

    _render_stakeholders(process, "ui.summary.process.stakeholders")
    _update_profile("process.stakeholders", process.get("stakeholders", []))

    _render_phases(
        process,
        process.get("stakeholders", []),
        "ui.summary.process.phases",
    )
    _update_profile("process.phases", process.get("phases", []))
    _update_profile("process.interview_stages", int(process.get("interview_stages") or 0))

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
    if original_timeline and not _parse_timeline_range(str(original_timeline))[0] and not changed:
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
        _render_onboarding_section(process, "ui.summary.process.onboarding", allow_generate=False)
        onboarding = process.get("onboarding_process", "")

    _update_profile("process.recruitment_timeline", timeline)
    _update_profile("process.process_notes", notes)
    _update_profile("process.application_instructions", instructions)
    _update_profile("process.onboarding_process", onboarding)
    _update_profile("process.hiring_manager_name", hiring_manager)
    _update_profile("process.hiring_manager_role", hiring_role)


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

        items_html = "".join(f"<li>{html.escape(entry_text)}</li>" for _, entry_text in entries)
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


def _normalize_range_bounds(min_value: float | None, max_value: float | None) -> tuple[float, float]:
    """Return a sorted pair of range bounds even when one side is missing."""

    values = [float(value) for value in (min_value, max_value) if value is not None]
    if not values:
        return 0.0, 0.0
    lower = min(values)
    upper = max(values)
    return lower, upper


def _build_salary_range_chart(
    *,
    expected_min: float | None,
    expected_max: float | None,
    user_min: float | None,
    user_max: float | None,
    currency: str,
) -> go.Figure | None:
    """Visualise the captured and benchmark salary ranges."""

    has_expected = expected_min is not None or expected_max is not None
    has_user = user_min is not None or user_max is not None
    if not (has_expected or has_user):
        return None

    figure = go.Figure()

    if has_expected:
        start, end = _normalize_range_bounds(expected_min, expected_max)
        length = max(end - start, 0.0)
        figure.add_trace(
            go.Bar(
                y=[tr("Marktbenchmark", "Market benchmark")],
                x=[length],
                base=start,
                orientation="h",
                name=tr("Erwartete Spanne", "Expected range"),
                marker=dict(
                    color="rgba(47, 216, 197, 0.65)",
                    line=dict(color="rgba(47, 216, 197, 0.95)", width=1.2),
                ),
                customdata=[[start, end]],
                hovertemplate=(
                    tr("Erwartete Spanne", "Expected range")
                    + f": %{{customdata[0]:,.0f}} – %{{customdata[1]:,.0f}} {currency}<extra></extra>"
                ),
            )
        )

    if has_user:
        start, end = _normalize_range_bounds(user_min, user_max)
        length = max(end - start, 0.0)
        figure.add_trace(
            go.Bar(
                y=[tr("Profilangabe", "Profile input")],
                x=[length],
                base=start,
                orientation="h",
                name=tr("Eingegebene Spanne", "Entered range"),
                marker=dict(
                    color="rgba(154, 166, 255, 0.6)",
                    line=dict(color="rgba(154, 166, 255, 0.9)", width=1.2),
                ),
                customdata=[[start, end]],
                hovertemplate=(
                    tr("Eingegebene Spanne", "Entered range")
                    + f": %{{customdata[0]:,.0f}} – %{{customdata[1]:,.0f}} {currency}<extra></extra>"
                ),
            )
        )

    axis_label = tr("Jahresgehalt ({currency})", "Annual salary ({currency})").format(currency=currency)
    figure.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=26, b=18),
        bargap=0.35,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="rgba(15,23,42,0.85)"),
    )
    figure.update_xaxes(
        title_text=axis_label,
        zeroline=False,
        gridcolor="rgba(148, 163, 184, 0.24)",
    )
    figure.update_yaxes(showgrid=False)
    return figure


def _first_text_value(value: object, lang_code: str) -> str:
    """Extract a readable string from nested API payload structures."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for code in (lang_code, "de", "en"):
            candidate = value.get(code)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            text = _first_text_value(item, lang_code)
            if text:
                return text
    return ""


def _extract_skill_description(payload: Mapping[str, Any], lang: str) -> str:
    """Return a human-friendly description from an ESCO skill payload."""

    lang_code = "de" if str(lang or "").lower().startswith("de") else "en"
    for key in ("description", "definition", "scopeNote", "conceptDefinition"):
        text = _first_text_value(payload.get(key), lang_code)
        if text:
            return text
    summary = _first_text_value(payload.get("summary"), lang_code)
    return summary


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_skill_metadata(skill: str, lang: str) -> dict[str, Any]:
    """Return cached ESCO metadata for ``skill``."""

    try:
        return lookup_esco_skill(skill, lang=lang)
    except Exception:  # pragma: no cover - defensive fallback
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_skill_description(uri: str, lang: str) -> str:
    """Fetch and cache ESCO skill details."""

    cleaned_uri = str(uri or "").strip()
    if not cleaned_uri:
        return ""
    params = {
        "uri": cleaned_uri,
        "language": "de" if str(lang or "").lower().startswith("de") else "en",
    }
    try:
        response = requests.get(ESCO_SKILL_ENDPOINT, params=params, timeout=6)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):  # pragma: no cover - network guard
        return ""
    if not isinstance(payload, Mapping):
        return ""
    return _extract_skill_description(payload, lang)


def _collect_skill_entries(data: Mapping[str, Any], lang: str) -> list[SkillInsightEntry]:
    """Collect unique skills from the profile for interactive exploration."""

    requirements = data.get("requirements", {}) if isinstance(data, Mapping) else {}
    if not isinstance(requirements, Mapping):
        return []
    missing_raw = st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
    missing = {str(item).strip().casefold() for item in missing_raw if isinstance(item, str) and str(item).strip()}
    is_de = str(lang or "").lower().startswith("de")
    entries: list[SkillInsightEntry] = []
    seen: set[str] = set()
    for key, labels in _SKILL_GROUP_LABELS.items():
        values = requirements.get(key, [])
        if not isinstance(values, Sequence):
            continue
        for value in values:
            label = str(value or "").strip()
            if not label:
                continue
            normalized = label.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            source_label = labels[0] if is_de else labels[1]
            entries.append(
                SkillInsightEntry(
                    label=label,
                    source_label=source_label,
                    category_key=key,
                    is_missing=normalized in missing,
                )
            )
    return entries


def _render_salary_insights(
    profile: NeedAnalysisProfile,
    raw_profile: Mapping[str, Any],
    *,
    lang: str,
) -> None:
    """Render the salary insights card with interactive visualisations."""

    compensation = raw_profile.get("compensation", {}) if isinstance(raw_profile, Mapping) else {}
    estimate: Mapping[str, Any] | None = st.session_state.get(UIKeys.SALARY_ESTIMATE)
    explanation = st.session_state.get(UIKeys.SALARY_EXPLANATION)
    timestamp: str | None = st.session_state.get(UIKeys.SALARY_REFRESH)

    est_min_raw = estimate.get("salary_min") if estimate else None
    est_max_raw = estimate.get("salary_max") if estimate else None
    est_currency_raw = estimate.get("currency") if estimate else None
    est_min = float(est_min_raw) if isinstance(est_min_raw, (int, float, str)) else None
    est_max = float(est_max_raw) if isinstance(est_max_raw, (int, float, str)) else None
    est_currency = str(est_currency_raw) if est_currency_raw else None

    user_min = profile.compensation.salary_min
    user_max = profile.compensation.salary_max
    user_currency = profile.compensation.currency or compensation.get("currency")
    currency = est_currency or user_currency or "EUR"

    metrics: list[str] = []
    if user_min is not None or user_max is not None:
        metrics.append(
            tr("Profil: {range}", "Profile: {range}").format(
                range=format_salary_range(user_min, user_max, currency),
            )
        )
    if est_min is not None or est_max is not None:
        metrics.append(
            tr("Benchmark: {range}", "Benchmark: {range}").format(
                range=format_salary_range(est_min, est_max, currency),
            )
        )

    figure = _build_salary_range_chart(
        expected_min=est_min,
        expected_max=est_max,
        user_min=float(user_min) if user_min is not None else None,
        user_max=float(user_max) if user_max is not None else None,
        currency=currency,
    )

    with st.container():
        st.markdown("<div class='insight-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='insight-card__header'><h4 class='insight-card__title'>💰 {tr('Gehalts-Insights', 'Salary insights')}</h4></div>",
            unsafe_allow_html=True,
        )
        if metrics:
            metric_html = "".join(f"<span>{html.escape(metric)}</span>" for metric in metrics)
            st.markdown(
                f"<div class='insight-card__metric'>{metric_html}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption(
                tr(
                    "Noch keine Gehaltsangaben vorhanden – ergänze Werte im Bereich ‘Beschäftigung’.",
                    "No salary data available yet – fill in the Employment section.",
                )
            )

        if figure is not None:
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
        else:
            st.info(
                tr(
                    "Sobald eine Spanne vorliegt, visualisieren wir sie hier inklusive Benchmark.",
                    "Once a range is available, it will appear here alongside the benchmark.",
                )
            )

        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                st.caption(
                    tr("Zuletzt aktualisiert: {ts}", "Last refreshed: {ts}").format(ts=dt.strftime("%d.%m.%Y %H:%M"))
                )
            except ValueError:
                pass

        if explanation:
            with st.expander(
                tr("Datenannahmen anzeigen", "View data assumptions"),
                expanded=False,
            ):
                if isinstance(explanation, str):
                    st.markdown(explanation)
                else:
                    st.json(explanation)

        st.markdown("</div>", unsafe_allow_html=True)


def _render_skill_insights(raw_profile: Mapping[str, Any], *, lang: str) -> None:
    """Render the interactive skill exploration card."""

    entries = _collect_skill_entries(raw_profile, lang)
    with st.container():
        st.markdown("<div class='insight-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='insight-card__header'><h4 class='insight-card__title'>🧠 {tr('Skill-Insights', 'Skill insights')}</h4></div>",
            unsafe_allow_html=True,
        )

        if not entries:
            st.caption(
                tr(
                    "Noch keine Skills erfasst – ergänze Anforderungen in den vorherigen Schritten.",
                    "No skills captured yet – add requirements in the earlier steps.",
                )
            )
            st.markdown("</div>", unsafe_allow_html=True)
            return

        highlight = "".join(
            "<span class='skill-badge{highlight}'>{label}</span>".format(
                highlight=" skill-badge--highlight" if entry.is_missing else "",
                label=html.escape(entry.label),
            )
            for entry in entries[:8]
        )
        st.markdown(
            f"<div class='skill-badge-list'>{highlight}</div>",
            unsafe_allow_html=True,
        )

        selected_entry = st.selectbox(
            tr("Skill auswählen", "Select skill"),
            options=entries,
            index=0,
            format_func=lambda entry: f"{entry.label} • {entry.source_label}",
            key="ui.summary.insights.skill_select",
            width="stretch",
        )

        metadata = _cached_skill_metadata(selected_entry.label, lang)
        resolved_label = metadata.get("preferredLabel") or selected_entry.label
        description = _cached_skill_description(str(metadata.get("uri")), lang) if metadata.get("uri") else ""

        st.markdown(f"**{tr('Bezeichnung', 'Label')}**: {resolved_label}")
        if description:
            st.markdown(f"**{tr('Beschreibung', 'Description')}**: {description}")
        else:
            st.caption(
                tr(
                    "Für diese Quelle liegt keine detaillierte ESCO-Beschreibung vor.",
                    "No detailed ESCO description is available for this entry.",
                )
            )

        skill_type_uri = str(metadata.get("skillType") or "")
        if skill_type_uri:
            type_key = skill_type_uri.rsplit("/", 1)[-1].lower()
            type_labels = _SKILL_TYPE_LABELS.get(type_key, (type_key.title(), type_key.title()))
            type_label = type_labels[0] if str(lang or "").lower().startswith("de") else type_labels[1]
            st.caption(tr("ESCO-Kategorie: {label}", "ESCO category: {label}").format(label=type_label))

        if metadata.get("uri"):
            st.caption(
                tr("Offizielle ESCO-Referenz: {uri}", "Official ESCO reference: {uri}").format(
                    uri=str(metadata.get("uri"))
                )
            )

        if selected_entry.is_missing:
            st.info(
                tr(
                    "ESCO markiert diesen Skill als noch offen – prüfe, ob er in Muss-Anforderungen gehört.",
                    "ESCO flagged this skill as outstanding – consider moving it into must-have requirements.",
                )
            )

        with st.expander(tr("Wie entstehen diese Empfehlungen?", "How are these insights generated?")):
            st.markdown(
                tr(
                    "Wir gleichen deine Angaben mit ESCO-Berufsprofilen ab und reichern die Listen mit offiziellen Beschreibungen an.",
                    "Your inputs are matched against ESCO occupation profiles and enriched with official descriptions.",
                )
            )
            st.markdown(
                tr(
                    "Fehlende Essentials erscheinen mit Hervorhebung – verschiebe sie in den passenden Abschnitt, um sie abzudecken.",
                    "Outstanding essentials are highlighted – move them into the appropriate requirement section to cover them.",
                )
            )
            if metadata:
                st.json(metadata)

        st.markdown("</div>", unsafe_allow_html=True)


def _render_summary_export_section(
    *,
    profile: NeedAnalysisProfile,
    profile_payload: Mapping[str, Any],
    raw_profile: Mapping[str, Any],
    lang: str,
    group_keys: Sequence[str],
    profile_bytes: bytes,
    profile_mime: str,
    profile_filename: str,
) -> None:
    """Render export, generation, and automation tools for the summary tab."""

    summary_data: dict[str, Any]
    if isinstance(raw_profile, dict):
        summary_data = raw_profile
    else:
        summary_data = dict(raw_profile)

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
    lang_code = st.session_state.get("lang", "de")
    selected_style = st.session_state.get(UIKeys.TONE_SELECT, STYLE_VARIANT_ORDER[1])
    if selected_style not in STYLE_VARIANTS:
        selected_style = STYLE_VARIANT_ORDER[1]
        st.session_state[UIKeys.TONE_SELECT] = selected_style
    variant = STYLE_VARIANTS.get(selected_style)
    preset_options = tone_presets.get(lang_code, {}) if isinstance(tone_presets, Mapping) else {}
    if variant is not None:
        style_instruction = preset_options.get(selected_style) or tr(*variant.instruction, lang=lang_code)
        st.session_state["tone"] = style_instruction
        st.session_state["style_prompt_hint"] = tr(*variant.prompt_hint, lang=lang_code)
        style_label = tr(*variant.label, lang=lang_code)
        style_description = tr(*variant.description, lang=lang_code)
        style_example = tr(*variant.example, lang=lang_code)
    else:
        style_instruction = str(selected_style)
        style_label = selected_style.replace("_", " ").title()
        style_description = ""
        style_example = ""
        st.session_state["tone"] = style_instruction
        st.session_state["style_prompt_hint"] = style_instruction

    base_url = st.session_state.get(StateKeys.COMPANY_PAGE_BASE) or ""
    style_reference = _job_ad_style_reference(profile_payload, base_url or None)

    suggestions = suggest_target_audiences(profile, lang)
    available_field_keys = _job_ad_available_field_keys(profile_payload, lang)

    target_value = st.session_state.get(StateKeys.JOB_AD_SELECTED_AUDIENCE, "")

    raw_selection = st.session_state.get(StateKeys.JOB_AD_SELECTED_FIELDS)
    widget_state_exists = any(f"{UIKeys.JOB_AD_FIELD_PREFIX}{group}" in st.session_state for group in group_keys)
    if raw_selection is None:
        current_selection: set[str] = set()
    else:
        current_selection = set(raw_selection)
    if not widget_state_exists and not current_selection:
        stored_selection = set(available_field_keys)
    else:
        stored_selection = {key for key in current_selection if key in available_field_keys}

    is_de = lang.lower().startswith("de")
    field_labels = {field.key: field.label_de if is_de else field.label_en for field in JOB_AD_FIELDS}

    render_section_heading(
        tr("Stellenanzeige erstellen", "Create a job ad"),
        icon="📝",
        description=tr(
            "Verwalte Inhalte, Tonalität und Optimierungen für deine Anzeige.",
            "Manage content, tone, and optimisations for your job ad.",
        ),
    )
    render_section_heading(
        tr("Feldauswahl", "Field selection"),
        size="compact",
        description=tr(
            "Wähle die Inhalte, die in die Stellenanzeige übernommen werden.",
            "Choose which sections should be included in the job ad.",
        ),
    )

    grouped_fields = [
        (
            group,
            [field for field in JOB_AD_FIELDS if field.group == group and field.key in available_field_keys],
        )
        for group in group_keys
    ]
    grouped_fields = [(group, fields) for group, fields in grouped_fields if fields]

    aggregated_selection: set[str] = set()
    columns_per_row = 2 if len(grouped_fields) > 1 else 1
    for start_index in range(0, len(grouped_fields), columns_per_row):
        row_groups = grouped_fields[start_index : start_index + columns_per_row]
        field_cols = st.columns(len(row_groups), gap="small")
        for column, (group, group_fields) in zip(field_cols, row_groups):
            with column:
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

                option_pairs = [(key, field_labels.get(key, key)) for key in options]
                selected_group_values = chip_multiselect_mapped(
                    widget_label,
                    option_pairs=option_pairs,
                    values=default_values,
                    state_key=widget_key,
                    add_more_hint=ADD_MORE_JOB_AD_FIELDS_HINT,
                )
                st.session_state[widget_key] = selected_group_values
                aggregated_selection.update(selected_group_values)

    selected_fields = resolve_job_ad_field_selection(available_field_keys, aggregated_selection)
    st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = set(selected_fields)

    with st.expander(tr("Präferenzen", "Preferences")):
        pref_cols = st.columns((1.4, 1.1, 1.2), gap="small")
        tone_col, export_col, branding_col = pref_cols

        with tone_col:
            render_section_heading(
                tr("Zielgruppe & Ton", "Audience & tone"),
                target=tone_col,
                size="micro",
            )
            st.markdown(f"**{tr('Ausgewählter Stil', 'Selected style')}**: {style_label}")
            if style_description:
                st.caption(style_description)
            if style_example:
                st.caption(style_example)
            brand_profile_value = raw_profile.get("company", {}).get("brand_keywords")
            brand_profile_text = brand_profile_value if isinstance(brand_profile_value, str) else ""
            if UIKeys.COMPANY_BRAND_KEYWORDS not in st.session_state and brand_profile_text:
                st.session_state[UIKeys.COMPANY_BRAND_KEYWORDS] = brand_profile_text

            company_brand_state = st.session_state.get(UIKeys.COMPANY_BRAND_KEYWORDS)
            if UIKeys.JOB_AD_BRAND_TONE not in st.session_state:
                initial_brand = company_brand_state if isinstance(company_brand_state, str) else brand_profile_text
                st.session_state[UIKeys.JOB_AD_BRAND_TONE] = (initial_brand or "").strip()

            stored_brand = (st.session_state.get(UIKeys.JOB_AD_BRAND_TONE) or "").strip()
            if UIKeys.JOB_AD_BRAND_TONE_INPUT not in st.session_state:
                st.session_state[UIKeys.JOB_AD_BRAND_TONE_INPUT] = stored_brand

            brand_value_input = st.text_input(
                tr("Brand-Ton oder Keywords", "Brand tone or keywords"),
                key=UIKeys.JOB_AD_BRAND_TONE_INPUT,
            )
            normalized_brand = brand_value_input.strip() if isinstance(brand_value_input, str) else stored_brand
            if normalized_brand:
                st.session_state[UIKeys.JOB_AD_BRAND_TONE] = normalized_brand
                _update_profile("company.brand_keywords", normalized_brand)
            else:
                st.session_state.pop(UIKeys.JOB_AD_BRAND_TONE, None)
                _update_profile("company.brand_keywords", None)

            profile_brand_comparable = brand_profile_text if isinstance(brand_profile_text, str) else ""
            if normalized_brand != profile_brand_comparable:
                st.session_state[UIKeys.JOB_AD_BRAND_TONE_SYNC_FLAG] = True
            else:
                st.session_state.pop(UIKeys.JOB_AD_BRAND_TONE_SYNC_FLAG, None)

            if suggestions:
                option_map = {suggestion.key: suggestion for suggestion in suggestions}
                option_keys = list(option_map.keys())
                if (
                    UIKeys.JOB_AD_TARGET_SELECT not in st.session_state
                    or st.session_state[UIKeys.JOB_AD_TARGET_SELECT] not in option_keys
                ):
                    st.session_state[UIKeys.JOB_AD_TARGET_SELECT] = option_keys[0]

                selected_key = st.selectbox(
                    tr("Zielgruppe auswählen", "Select target audience"),
                    options=option_keys,
                    format_func=lambda key: f"{option_map[key].title} – {option_map[key].description}",
                    key=UIKeys.JOB_AD_TARGET_SELECT,
                    width="stretch",
                )
                chosen = option_map.get(selected_key, suggestions[0])
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

        with export_col:
            render_section_heading(
                tr("Exportoptionen", "Export options"),
                target=export_col,
                size="micro",
            )
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
                width="stretch",
            )

            font_default = st.session_state.get(StateKeys.JOB_AD_FONT_CHOICE, FONT_CHOICES[0])
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
                width="stretch",
            )
            st.caption(
                tr(
                    "Die Auswahl gilt für Stellenanzeige und Interviewleitfaden, sofern unterstützt.",
                    "Selection applies to job ad and interview guide when supported.",
                )
            )

        with branding_col:
            render_section_heading(
                tr("Branding-Assets", "Brand assets"),
                target=branding_col,
                size="micro",
            )
            logo_file = st.file_uploader(
                tr("Logo hochladen (optional)", "Upload logo (optional)"),
                type=["png", "jpg", "jpeg", "svg"],
                key=UIKeys.JOB_AD_LOGO_UPLOAD,
            )
            if logo_file is not None:
                _set_company_logo(logo_file.getvalue())
            logo_bytes = _get_company_logo_bytes()
            if logo_bytes:
                try:
                    st.image(logo_bytes, caption=tr("Aktuelles Logo", "Current logo"), width=180)
                except Exception:
                    st.caption(tr("Logo erfolgreich geladen.", "Logo uploaded successfully."))
                if st.button(tr("Logo entfernen", "Remove logo"), key="job_ad_logo_remove"):
                    _set_company_logo(None)
                    st.rerun()

    st.divider()

    st.session_state[StateKeys.JOB_AD_SELECTED_AUDIENCE] = target_value

    filtered_profile = _prepare_job_ad_data(profile_payload)
    filtered_profile["lang"] = lang

    manual_entries: list[dict[str, str]] = list(st.session_state.get(StateKeys.JOB_AD_MANUAL_ENTRIES, []))
    with st.expander(tr("Manuelle Ergänzungen", "Manual additions")):
        manual_title = st.text_input(
            tr("Titel (optional)", "Title (optional)"),
            key=UIKeys.JOB_AD_MANUAL_TITLE,
            placeholder=tr("z. B. wichtigste Erfolge", "e.g. Key achievements"),
        )
        manual_text = st.text_area(
            tr("Freitext", "Free text"),
            key=UIKeys.JOB_AD_MANUAL_TEXT,
            placeholder=tr(
                "Lade ein PDF hoch oder füge hier Highlights, KPIs oder Zusatzinfos ein …",
                "Upload a PDF or paste highlights, KPIs, or extra context here…",
            ),
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
                title = entry.get("title") or tr("Zusätzliche Information", "Additional information")
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
    llm_available = is_llm_available()
    disabled = not has_content or not target_value or not llm_available
    if not llm_available:
        st.caption(llm_disabled_message())
    if st.button(
        tr("📝 Stellenanzeige generieren", "📝 Generate job ad"),
        disabled=disabled,
        type="primary",
    ):
        generate_job_ad_content(
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
    if output_key not in st.session_state or st.session_state[output_key] != display_text:
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
                    st.write(tr("Top-Schlüsselbegriffe", "Top keywords") + ": " + ", ".join(keywords))
                if meta_description:
                    st.write(tr("Meta-Beschreibung", "Meta description") + ": " + meta_description)

        findings = st.session_state.get(StateKeys.BIAS_FINDINGS) or []
        if findings:
            with st.expander(tr("Bias-Check", "Bias check")):
                for finding in findings:
                    st.warning(finding)

        format_choice = st.session_state.get(UIKeys.JOB_AD_FORMAT, "markdown")
        font_choice = st.session_state.get(StateKeys.JOB_AD_FONT_CHOICE)
        logo_bytes = _get_company_logo_bytes()
        company_name = (
            profile.company.brand_name
            or profile.company.name
            or str(_job_ad_get_value(profile_payload, "company.name") or "").strip()
            or None
        )
        job_title = (
            profile.position.job_title
            or str(_job_ad_get_value(profile_payload, "position.job_title") or "").strip()
            or "job-ad"
        )
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", job_title).strip("-") or "job-ad"
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

        render_section_heading(
            tr("Anpassungswünsche", "Refinement requests"),
            size="micro",
        )
        feedback = st.text_area(
            tr("Was soll angepasst werden?", "What should be adjusted?"),
            key=UIKeys.JOB_AD_FEEDBACK,
        )
        refine_disabled = not llm_available
        if not llm_available:
            st.caption(llm_disabled_message())
        if st.button(
            tr("🔄 Anzeige anpassen", "🔄 Refine job ad"),
            key=UIKeys.REFINE_JOB_AD,
            disabled=refine_disabled,
        ):
            try:
                refined = refine_document(job_ad_text, feedback)
                st.session_state[StateKeys.JOB_AD_MD] = refined
                findings = scan_bias_language(refined, st.session_state.lang)
                st.session_state[StateKeys.BIAS_FINDINGS] = findings
                st.rerun()
            except Exception as e:
                st.error(tr("Verfeinerung fehlgeschlagen", "Refinement failed") + f": {e}")

    render_interview_guide_section(
        profile,
        profile_payload,
        lang=lang,
        style_label=style_label,
        style_description=style_description,
    )

    render_section_heading(tr("Boolean Searchstring", "Boolean search string"), icon="🔎")
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

    st.divider()

    manual_entries = list(st.session_state.get(StateKeys.JOB_AD_MANUAL_ENTRIES, []))

    followup_items = st.session_state.get(StateKeys.FOLLOWUPS) or []
    if followup_items:
        st.markdown(tr("**Vorgeschlagene Fragen:**", "**Suggested questions:**"))

        entry_specs: list[tuple[str, str]] = []
        for item in followup_items:
            field_path = item.get("field") or item.get("key") or ""
            question_text = item.get("question") or ""
            if not field_path or not question_text:
                continue
            entry_specs.append((field_path, question_text))

        if entry_specs:
            stored_snapshot = dict(st.session_state.get(StateKeys.SUMMARY_FOLLOWUP_SNAPSHOT, {}))
            with st.form("summary_followups_form"):
                for field_path, question_text in entry_specs:
                    st.markdown(f"**{question_text}**")
                    profile_text_input(
                        field_path,
                        question_text,
                        key=f"fu_{field_path}",
                        label_visibility="collapsed",
                        allow_callbacks=False,
                    )
                submit_label = tr(
                    "Folgeantworten anwenden",
                    "Apply follow-up answers",
                )
                submitted = st.form_submit_button(submit_label, type="primary")

            if submitted:
                answers = {
                    field_path: st.session_state.get(f"fu_{field_path}", "") for field_path, _question in entry_specs
                }
                trimmed_answers = {field: value.strip() for field, value in answers.items()}
                for field_path, value in trimmed_answers.items():
                    if value:
                        _update_profile(field_path, value)
                changed = trimmed_answers != stored_snapshot
                st.session_state[StateKeys.SUMMARY_FOLLOWUP_SNAPSHOT] = trimmed_answers

                if changed:
                    job_generated, interview_generated = _apply_followup_updates(
                        trimmed_answers,
                        data=summary_data,
                        filtered_profile=filtered_profile,
                        profile_payload=profile_payload,
                        target_value=target_value,
                        manual_entries=manual_entries,
                        style_reference=style_reference,
                        lang=lang,
                        selected_fields=selected_fields,
                        num_questions=st.session_state.get(UIKeys.NUM_QUESTIONS, 5),
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

    st.divider()
    st.download_button(
        tr("⬇️ JSON-Profil exportieren", "⬇️ Export JSON profile"),
        profile_bytes,
        file_name=profile_filename,
        mime=profile_mime,
        width="stretch",
        key="download_profile_json",
    )


def _step_summary(_schema: dict, _critical: list[str]) -> None:
    """Render the summary step and offer follow-up questions.

    Args:
        schema: Schema defining allowed fields.
        critical: Keys that must be present in ``data``.

    Returns:
        None
    """

    st.markdown(COMPACT_STEP_STYLE, unsafe_allow_html=True)

    profile_state = st.session_state.get(StateKeys.PROFILE)
    summary_data: dict[str, Any] = {}
    if isinstance(profile_state, dict):
        summary_data = profile_state
    elif isinstance(profile_state, Mapping):
        summary_data = dict(profile_state)
        st.session_state[StateKeys.PROFILE] = summary_data
    else:
        ensure_state()
        refreshed = st.session_state.get(StateKeys.PROFILE)
        summary_data = refreshed if isinstance(refreshed, dict) else {}
    data = summary_data
    lang = st.session_state.get("lang", "de")

    try:
        profile = coerce_and_fill(data)
    except ValidationError:
        profile = NeedAnalysisProfile()

    profile_payload = profile.model_dump(mode="json")
    profile_payload["lang"] = lang

    profile_bytes, profile_mime, profile_ext = prepare_clean_json(profile_payload)
    job_title_value = (profile.position.job_title or "").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", job_title_value).strip("-")
    if not safe_stem:
        safe_stem = "need-analysis-profile"
    profile_filename = f"{safe_stem}.{profile_ext}"

    title, subtitle, intros = _resolve_step_copy("summary", data)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)

    _render_followups_for_step("summary", data)

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

    tab_definitions = list(zip(group_keys, tab_labels))
    summary_helpers: dict[str, Callable[[], None]] = {
        "company": _summary_company,
        "basic": _summary_position,
        "requirements": _summary_requirements,
        "employment": _summary_employment,
        "compensation": _summary_compensation,
        "process": _summary_process,
    }

    overview_label = tr("📋 Überblick", "📋 Overview")
    insights_label = tr("✨ Insights", "✨ Insights")
    export_label = tr("📤 Export & Aktionen", "📤 Export & actions")
    overview_tab, insights_tab, export_tab = st.tabs([overview_label, insights_label, export_label])

    with overview_tab:
        edit_title = tr("Angaben bearbeiten", "Edit captured details")
        render_section_heading(edit_title, icon="🛠️")
        st.caption(
            tr(
                "Passe die Inhalte der einzelnen Bereiche direkt in den Tabs an.",
                "Adjust the contents of each section directly within the tabs.",
            )
        )

        section_tabs = st.tabs([label for _, label in tab_definitions])
        for tab, (group, _label) in zip(section_tabs, tab_definitions):
            with tab:
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

    with insights_tab:
        _render_salary_insights(profile, profile_payload, lang=lang)
        _render_skill_insights(profile_payload, lang=lang)

    with export_tab:
        _render_summary_export_section(
            profile=profile,
            profile_payload=profile_payload,
            raw_profile=data,
            lang=lang,
            group_keys=tuple(group_keys),
            profile_bytes=profile_bytes,
            profile_mime=profile_mime,
            profile_filename=profile_filename,
        )


# --- Navigation helper ---


# --- Haupt-Wizard-Runner ---
def _load_wizard_configuration() -> tuple[dict, list[str]]:
    """Return schema and critical field configuration from state or disk."""

    schema: dict = st.session_state.get("_schema") or {}
    critical: list[str] = st.session_state.get("_critical_list") or []

    if not schema:
        try:
            with (ROOT / "schema" / "need_analysis.schema.json").open("r", encoding="utf-8") as file:
                schema = json.load(file)
        except Exception:
            schema = {}
    if not critical:
        try:
            with (ROOT / "critical_fields.json").open("r", encoding="utf-8") as file:
                critical = json.load(file).get("critical", [])
        except Exception:
            critical = []
    return schema, critical


def _render_jobad_step_v2(schema: Mapping[str, object]) -> None:
    _render_onboarding_hero()
    _step_onboarding(dict(schema))


def _render_skills_review_step() -> None:
    profile = _get_profile_state()
    lang = st.session_state.get("lang", "de")
    title, subtitle, intros = _resolve_step_copy("skills", profile)
    render_step_heading(title, subtitle)
    for intro in intros:
        st.caption(intro)
    responsibilities = profile.get("responsibilities", {}) if isinstance(profile, Mapping) else {}
    requirement_data = profile.get("requirements", {}) if isinstance(profile, Mapping) else {}

    resp_items = []
    if isinstance(responsibilities, Mapping):
        resp_items = [
            str(item).strip() for item in responsibilities.get("items", []) if isinstance(item, str) and item.strip()
        ]
    if resp_items:
        st.markdown("\n".join(f"- {item}" for item in resp_items))
    else:
        st.info(tr("Noch keine Aufgaben hinterlegt.", "No responsibilities captured yet."))

    def _render_chip_group(title_de: str, title_en: str, values: Iterable[str]) -> None:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        title = title_de if lang.lower().startswith("de") else title_en
        st.markdown(f"**{title}**")
        if not cleaned:
            st.caption(tr("Keine Einträge", "No entries"))
            return
        chips = "".join(f"<span class='wizard-chip'>{html.escape(value)}</span>" for value in cleaned)
        st.markdown(f"<div class='wizard-chip-list'>{chips}</div>", unsafe_allow_html=True)

    if isinstance(requirement_data, Mapping):
        _render_chip_group(
            "Muss-Hard-Skills",
            "Must-have hard skills",
            requirement_data.get("hard_skills_required", []),
        )
        _render_chip_group(
            "Muss-Soft-Skills",
            "Must-have soft skills",
            requirement_data.get("soft_skills_required", []),
        )
        _render_chip_group(
            "Tools & Technologien",
            "Tools & technologies",
            requirement_data.get("tools_and_technologies", []),
        )
        _render_chip_group(
            "Sprachen",
            "Languages",
            requirement_data.get("languages_required", []),
        )


def step_jobad(context: WizardContext) -> None:
    """Render the job ad intake step using ``context``."""

    _render_jobad_step_v2(context.schema)


def step_company(context: WizardContext) -> None:
    """Render the company step."""

    _step_company()


def step_team(context: WizardContext) -> None:
    """Render the team/position step."""

    _step_position()


def step_role_tasks(context: WizardContext) -> None:
    """Render the role tasks step."""

    _step_requirements()


def step_skills(context: WizardContext) -> None:
    """Render the skills review step."""

    _render_skills_review_step()


def step_benefits(context: WizardContext) -> None:
    """Render the benefits and compensation step."""

    _step_compensation()


def step_interview(context: WizardContext) -> None:
    """Render the interview/process step."""

    _step_process()


def step_summary(context: WizardContext) -> None:
    """Render the summary step using ``context`` for schema and critical fields."""

    _step_summary(dict(context.schema), list(context.critical_fields))


STEP_SEQUENCE: tuple[WizardStepDescriptor, ...] = (
    WizardStepDescriptor(WizardStepKey.JOBAD, StepRenderer(step_jobad, legacy_index=0)),
    WizardStepDescriptor(WizardStepKey.COMPANY, StepRenderer(step_company, legacy_index=1)),
    WizardStepDescriptor(WizardStepKey.TEAM, StepRenderer(step_team, legacy_index=2)),
    WizardStepDescriptor(
        WizardStepKey.ROLE_TASKS,
        StepRenderer(step_role_tasks, legacy_index=3),
    ),
    WizardStepDescriptor(WizardStepKey.SKILLS, StepRenderer(step_skills, legacy_index=4)),
    WizardStepDescriptor(
        WizardStepKey.BENEFITS,
        StepRenderer(step_benefits, legacy_index=5),
    ),
    WizardStepDescriptor(
        WizardStepKey.INTERVIEW,
        StepRenderer(step_interview, legacy_index=6),
    ),
    WizardStepDescriptor(WizardStepKey.SUMMARY, StepRenderer(step_summary, legacy_index=7)),
)

STEP_RENDERERS: dict[str, StepRenderer] = {descriptor.key.value: descriptor.renderer for descriptor in STEP_SEQUENCE}


def _run_wizard_v2(schema: Mapping[str, object], critical: Sequence[str]) -> None:
    st.session_state[StateKeys.WIZARD_STEP_COUNT] = len(WIZARD_PAGES)
    _update_section_progress()

    context = WizardContext(schema=schema, critical_fields=critical)
    router = WizardRouter(
        pages=WIZARD_PAGES,
        renderers=STEP_RENDERERS,
        context=context,
        value_resolver=get_in,
    )
    router.run()
    _apply_pending_scroll_reset()


def _render_admin_debug_panel() -> None:
    """Render the admin debug controls when enabled via configuration."""

    if not app_config.ADMIN_DEBUG_PANEL:
        return

    expanded = bool(st.session_state.get(UIKeys.DEBUG_DETAILS))
    with st.expander(
        tr("🛠️ Admin-Debug-Panel", "🛠️ Admin debug panel"),
        expanded=expanded,
    ):
        st.caption(
            tr(
                "Nur für Administrator:innen sichtbar – beeinflusst LLM-Routing und Debug-Ausgaben.",
                "Visible to administrators only – adjusts LLM routing and debug output.",
            )
        )
        debug_col, api_col, tools_col = st.columns((1, 1.2, 1))
        debug_enabled = debug_col.checkbox(
            tr("Debugmodus aktivieren", "Enable debug mode"),
            value=bool(st.session_state.get("debug")),
            key=UIKeys.DEBUG_PANEL,
            help=tr(
                "Zeigt detaillierte Fehlermeldungen und Stacktraces direkt im Wizard an.",
                "Surfaces detailed error messages and stack traces directly inside the wizard.",
            ),
        )
        st.session_state["debug"] = bool(debug_enabled)
        st.session_state[UIKeys.DEBUG_DETAILS] = bool(debug_enabled)
        if debug_enabled:
            debug_col.caption(
                tr(
                    "Aktiviert ausführliche Logs für API-Aufrufe, Extraktion und Follow-ups.",
                    "Enables verbose logs for API calls, extraction, and follow-ups.",
                )
            )

        mode_options: tuple[str, ...] = ("responses", "chat")
        mode_labels = {
            "responses": tr("Responses-API", "Responses API"),
            "chat": tr("Chat-Completions-API", "Chat Completions API"),
        }
        current_mode = "chat" if app_config.USE_CLASSIC_API else "responses"
        stored_mode = str(st.session_state.get(UIKeys.DEBUG_API_MODE) or current_mode)
        if stored_mode not in mode_labels:
            stored_mode = current_mode
        selected_mode = api_col.radio(
            tr("API-Modus", "API mode"),
            options=mode_options,
            index=mode_options.index(stored_mode),
            key=UIKeys.DEBUG_API_MODE,
            format_func=lambda value: mode_labels.get(value, value.title()),
            horizontal=True,
        )
        if selected_mode != current_mode:
            set_api_mode(selected_mode == "responses")
            st.toast(
                tr("Responses-API aktiv.", "Responses API active.")
                if selected_mode == "responses"
                else tr("Chat-Completions-API aktiv.", "Chat Completions API active."),
                icon="🔁",
            )

        allow_tools = bool(app_config.RESPONSES_ALLOW_TOOLS)
        requested_allow = tools_col.checkbox(
            tr("Responses-Tools erlauben", "Allow Responses tools"),
            value=allow_tools,
            key="ui.debug.allow_tools",
            help=tr(
                "Schaltet Funktions- und Toolaufrufe für Responses frei (nur wenn vom Account unterstützt).",
                "Enables function/tool payloads for Responses (only if your account is allow-listed).",
            ),
        )
        if bool(requested_allow) != allow_tools:
            set_responses_allow_tools(bool(requested_allow))
            st.toast(
                tr("Responses-Tools aktiviert.", "Responses tools enabled.")
                if requested_allow
                else tr("Responses-Tools deaktiviert.", "Responses tools disabled."),
                icon="🧩",
            )
        tools_col.caption(
            tr(
                "Erfordert eine freigeschaltete Responses-Instanz – andernfalls fällt der Client automatisch auf Chat zurück.",
                "Requires an allow-listed Responses tenant – otherwise the client falls back to Chat automatically.",
            )
        )


def run_wizard() -> None:
    """Run the multi-step profile creation wizard."""

    st.markdown(WIZARD_LAYOUT_STYLE, unsafe_allow_html=True)
    schema, critical = _load_wizard_configuration()
    _render_admin_debug_panel()
    try:
        _run_wizard_v2(schema, critical)
    except (RerunException, StopException):  # pragma: no cover - Streamlit control flow
        raise
    except _RECOVERABLE_FLOW_ERRORS as error:
        logger.warning("Recoverable wizard error", exc_info=error)
        _render_localized_error(
            "Der Wizard konnte nicht vollständig geladen werden. Bitte prüfe deine Eingaben oder ergänze sie manuell – die Sitzung bleibt aktiv.",
            "The wizard could not finish loading. Please review your answers or keep editing the profile manually – your session stays active.",
            error,
        )
    except Exception as error:  # pragma: no cover - defensive guard
        logger.exception("Unexpected wizard failure", exc_info=error)
        _render_localized_error(
            "Ein unerwarteter Fehler ist aufgetreten. Aktualisiere den Schritt oder fülle die Felder manuell aus.",
            "An unexpected error occurred. Refresh the step or continue filling the fields manually.",
            error,
        )
