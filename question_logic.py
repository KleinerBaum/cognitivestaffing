"""Adaptive follow-up question logic with ESCO + optional RAG enrichment.

- ESCO occupation lookups and essential skill retrieval seed field-level
  follow-ups and suggestions alongside RAG context when available.
- Asks the LLM to produce compact, localized questions with priority flags and
  options.

Outputs (for UI sorting and chips):
[
  {
    "field": "compensation.salary_min",
    "question": "...",
    "priority": "critical" | "normal" | "optional",
    "suggestions": ["…", "…"]         # optional
  },
  ...
]
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple, cast

import streamlit as st
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from utils.i18n import tr
from i18n import t as translate_key


def call_chat_api(*args: Any, **kwargs: Any) -> Any:
    """Proxy to lazily import :func:`wizard._openai_bridge.call_chat_api`."""

    from wizard._openai_bridge import call_chat_api as _call_chat_api

    return _call_chat_api(*args, **kwargs)


def build_file_search_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Proxy to lazily import :func:`wizard._openai_bridge.build_file_search_tool`."""

    from wizard._openai_bridge import build_file_search_tool as _build_file_search_tool

    return _build_file_search_tool(*args, **kwargs)


# ESCO helpers (core utils + offline-aware wrapper)
from constants.keys import ProfilePaths, StateKeys
from core.critical_fields import load_critical_fields
from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    get_group_skills,
    normalize_skill_map,
    normalize_skills,
    skill_casefold_key,
    lookup_esco_skill,
)
from core.validation import is_placeholder
from core.suggestions import get_benefit_suggestions
from config import (
    VECTOR_STORE_ID,
    ModelTask,
    get_active_verbosity,
    get_model_for,
    is_llm_enabled,
)
from prompts import prompt_registry
from wizard.planner.plan_context import PlanContext
from wizard.planner.role_overlays import canonicalize_role_key, get_role_overlay_questions
from wizard.services.followups import FollowupModelConfig, generate_followups as generate_followups_service

# Optional OpenAI vector store ID for RAG suggestions; set via env/secrets.
# If unset or blank, RAG lookups are skipped.
RAG_VECTOR_STORE_ID = VECTOR_STORE_ID

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _critical_fields() -> frozenset[str]:
    """Return critical field paths for follow-up prioritization."""

    current = CRITICAL_FIELDS
    if isinstance(current, _LazyCriticalFields):
        return current._values()
    return frozenset(current)


class _LazyCriticalFields(Set[str]):
    """Set-like lazy view over shared critical fields."""

    def _values(self) -> frozenset[str]:
        return frozenset(load_critical_fields())

    def __contains__(self, value: object) -> bool:
        return value in self._values()

    def __iter__(self):
        return iter(self._values())

    def __len__(self) -> int:
        return len(self._values())


CRITICAL_FIELDS: Set[str] = _LazyCriticalFields()


@st.cache_data(show_spinner=False)
def _load_role_field_map() -> dict[str, list[str]]:
    """Load role-to-field mappings lazily from disk."""

    root = Path(__file__).resolve().parent
    with (root / "role_field_map.json").open("r", encoding="utf-8") as file:
        payload = json.load(file)
    role_fields: dict[str, list[str]] = {}
    for key, value in payload.items():
        if not isinstance(value, list):
            continue
        canonical_key = canonicalize_role_key(key)
        if not canonical_key:
            continue
        role_fields[canonical_key] = list(value)
    return role_fields


def _resolve_role_questions(group_key: str, lang: str) -> List[Dict[str, str]]:
    """Return localized role-specific follow-up question entries."""

    resolved: List[Dict[str, str]] = []
    for item in get_role_overlay_questions(group_key):
        field = item.get("field")
        if not field:
            continue
        text_key = item.get("text_key")
        if text_key:
            question = translate_key(text_key, lang)
        else:
            question = str(item.get("question") or "").strip()
        if not question:
            continue
        resolved.append({"field": field, "question": question})
    return resolved


SKILL_FIELDS: Set[str] = {
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
}

ESCO_ESSENTIAL_FIELDS: Tuple[str, ...] = (
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
)

ESCO_SKILL_TARGET_FIELDS: Tuple[str, ...] = (
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
)

YES_NO_FIELDS: Set[str] = {
    str(ProfilePaths.COMPENSATION_VARIABLE_PAY),
    str(ProfilePaths.COMPENSATION_EQUITY_OFFERED),
    str(ProfilePaths.EMPLOYMENT_TRAVEL_REQUIRED),
    str(ProfilePaths.EMPLOYMENT_OVERTIME_EXPECTED),
    str(ProfilePaths.EMPLOYMENT_RELOCATION_SUPPORT),
    str(ProfilePaths.EMPLOYMENT_SECURITY_CLEARANCE_REQUIRED),
    str(ProfilePaths.EMPLOYMENT_SHIFT_WORK),
    str(ProfilePaths.EMPLOYMENT_VISA_SPONSORSHIP),
    str(ProfilePaths.REQUIREMENTS_BACKGROUND_CHECK_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_PORTFOLIO_REQUIRED),
    str(ProfilePaths.REQUIREMENTS_REFERENCE_CHECK_REQUIRED),
}

DEFAULT_BENEFIT_SUGGESTIONS: Dict[str, List[str]] = {
    "en": [
        "Health insurance",
        "Retirement plan",
        "Company car",
        "Annual bonus",
        "Training budget",
        "Hybrid work setup",
    ],
    "de": [
        "Betriebliche Altersvorsorge",
        "Dienstwagen",
        "Jährlicher Bonus",
        "Weiterbildungsbudget",
        "Mobiles Arbeiten",
        "ÖPNV-Zuschuss",
    ],
}

MAX_FOLLOWUP_QUESTIONS = 12


SALARY_PREFIX = str(ProfilePaths.COMPENSATION_SALARY_MIN).rsplit("_", 1)[0]
HARD_SKILLS_PREFIX = str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED).rsplit("_", 1)[0]
SOFT_SKILLS_PREFIX = str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED).rsplit("_", 1)[0]


def _value_to_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "")


def _get_field_value(extracted: Dict[str, Any], path: str, default: Any = None) -> Any:
    if path in extracted:
        return extracted[path]
    cursor: Any = extracted
    for part in path.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return default
    return cursor


def _existing_value_keys(extracted: Dict[str, Any], path: str) -> Set[str]:
    raw = _get_field_value(extracted, path, None)
    values: Iterable[Any]
    if isinstance(raw, (list, tuple, set)):
        values = raw
    elif raw is None:
        values = []
    else:
        values = [raw]
    normalized: Set[str] = set()
    for item in values:
        text = str(item).strip()
        if text:
            normalized.add(skill_casefold_key(text))
    return normalized


def _existing_esco_uris_for_field(extracted: Dict[str, Any], field_path: str) -> Set[str]:
    """Return ESCO URIs already bound to ``field_path`` skill mappings."""

    requirements = extracted.get("requirements") if isinstance(extracted, dict) else None
    if not isinstance(requirements, dict):
        return set()
    mappings = requirements.get("skill_mappings")
    if not isinstance(mappings, dict):
        return set()
    key = field_path.replace("requirements.", "", 1)
    entries = mappings.get(key)
    if not isinstance(entries, list):
        return set()
    uris: Set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        uri = str(entry.get("esco_uri") or "").strip()
        if uri:
            uris.add(uri)
    return uris


def _build_esco_skill_entry(skill: str, lang: str) -> Dict[str, str]:
    """Build a structured ESCO skill entry for follow-up state."""

    normalized_label = normalize_skills([skill], lang=lang)
    label = normalized_label[0] if normalized_label else str(skill).strip()
    meta = lookup_esco_skill(label, lang=lang)
    uri = str(meta.get("uri") or "").strip()
    skill_type = str(meta.get("skillType") or "").strip()
    entry: Dict[str, str] = {"label": label}
    if uri:
        entry["uri"] = uri
    if skill_type:
        entry["skill_type"] = skill_type
    return entry


def _merge_suggestions(*iterables: Iterable[str], existing: Optional[Set[str]] = None) -> List[str]:
    seen = set(existing or set())
    merged: List[str] = []
    for iterable in iterables:
        for item in iterable or []:
            text = str(item).strip()
            if not text:
                continue
            key = skill_casefold_key(text)
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
    return merged


def _coerce_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", ".").strip()
            if not cleaned:
                return None
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return None


def _detect_implausible(field: str, value: Any) -> Optional[Tuple[str, Any]]:
    if _is_empty(value):
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value if str(v).strip()]
        if items and all(is_placeholder(v) for v in items):
            return ("placeholder", items)
        return None
    if isinstance(value, str) and is_placeholder(value):
        return ("placeholder", value)
    if field.startswith(SALARY_PREFIX):
        numeric = _coerce_to_float(value)
        if numeric is not None and numeric <= 0:
            return ("salary_unrealistic", numeric)
    return None


def _question_text_for_field(field: str, lang: str, reason: Optional[Tuple[str, Any]]) -> str:
    label = field.split(".")[-1].replace("_", " ")
    if field in {str(ProfilePaths.COMPENSATION_SALARY_MIN), str(ProfilePaths.COMPENSATION_SALARY_MAX)}:
        if reason and reason[0] == "salary_unrealistic":
            base = tr(
                "Die bisherige Gehaltsangabe wirkt ungewöhnlich. Wie lautet die realistische Gehaltsspanne (Min/Max) inklusive Währung?",
                "The current salary details look unusual. What is the accurate salary range (min/max) including currency?",
                lang=lang,
            )
        else:
            base = tr(
                "Wie lautet die Gehaltsspanne (Min/Max) und die Währung für diese Position?",
                "What is the salary range (min and max) and currency for this position?",
                lang=lang,
            )
    elif field.startswith("responsibilities."):
        base = tr(
            "Welche zentralen Aufgaben oder Verantwortlichkeiten hat die Rolle?",
            "Could you list the key responsibilities or tasks for this role?",
            lang=lang,
        )
    elif field.startswith(HARD_SKILLS_PREFIX):
        base = tr(
            "Welche Hard Skills oder technischen Kompetenzen werden benötigt?",
            "What hard skills or technical competencies are required?",
            lang=lang,
        )
    elif field.startswith(SOFT_SKILLS_PREFIX):
        base = tr(
            "Welche Soft Skills oder zwischenmenschlichen Fähigkeiten sind wichtig?",
            "What soft skills or interpersonal skills are important?",
            lang=lang,
        )
    elif field.startswith(str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES)):
        base = tr(
            "Mit welchen Tools und Technologien sollte der Kandidat vertraut sein?",
            "Which tools and technologies should the candidate be familiar with?",
            lang=lang,
        )
    elif field == str(ProfilePaths.REQUIREMENTS_LANGUAGE_LEVEL_ENGLISH):
        base = tr(
            "Welches Englischniveau wird benötigt (z. B. B2, C1)?",
            "What English proficiency level is required (e.g., B2, C1)?",
            lang=lang,
        )
    elif field == str(ProfilePaths.LOCATION_PRIMARY_CITY):
        base = tr(
            "In welcher Stadt ist die Position angesiedelt?",
            "In which city is this position based?",
            lang=lang,
        )
    elif field == str(ProfilePaths.LOCATION_COUNTRY):
        base = tr(
            "In welchem Land ist die Position angesiedelt?",
            "In which country is this position located?",
            lang=lang,
        )
    elif field == str(ProfilePaths.COMPANY_CONTACT_PHONE):
        base = tr(
            "Unter welcher Telefonnummer können sich Kandidat:innen melden?",
            "What is the best contact phone number for candidates to reach out?",
            lang=lang,
        )
    elif field == str(ProfilePaths.COMPENSATION_BENEFITS):
        base = tr(
            "Welche Zusatzleistungen bietet das Unternehmen (z. B. betriebliche Altersvorsorge, Dienstwagen)?",
            "Which benefits does the company offer (e.g., retirement plan, company car)?",
            lang=lang,
        )
    else:
        base = tr(
            "Bitte geben Sie {label} an.",
            "Please provide the {label}.",
            lang=lang,
        ).format(label=label)
    if (
        reason
        and reason[0] == "placeholder"
        and field not in {str(ProfilePaths.COMPENSATION_SALARY_MIN), str(ProfilePaths.COMPENSATION_SALARY_MAX)}
    ):
        base = tr(
            "Die aktuelle Angabe wirkt wie ein Platzhalter. Bitte ergänzen Sie {label}.",
            "The current entry looks like a placeholder. Please provide the {label}.",
            lang=lang,
        ).format(label=label)
    return base if base.endswith("?") else base + "?"


def _get_followups_answered(extracted: Dict[str, Any]) -> List[str]:
    raw = _get_field_value(extracted, str(ProfilePaths.META_FOLLOWUPS_ANSWERED), [])
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str)]
    if isinstance(raw, str):
        return [raw]
    return []


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return len(val.strip()) == 0
    if isinstance(val, (list, tuple, set)):
        return len(val) == 0
    # Note: bool False is not "empty" for our purposes (treated as provided)
    return False


def _priority_for(
    field: str,
    is_missing_esco_skill: bool = False,
    reason: Optional[Tuple[str, Any]] = None,
) -> str:
    if reason and reason[0] == "salary_unrealistic":
        return "critical"
    if is_missing_esco_skill:
        return "critical"
    if field in _critical_fields():
        return "critical"
    return "normal"


def _collect_missing_fields(
    extracted: Dict[str, Any],
    fields: List[str],
    *,
    answered: Optional[Set[str]] = None,
) -> Tuple[List[str], Dict[str, Tuple[str, Any]]]:
    missing: List[str] = []
    implausible: Dict[str, Tuple[str, Any]] = {}
    answered = answered or set()
    for f in fields:
        if f in answered:
            continue
        value = _get_field_value(extracted, f, None)
        if _is_empty(value):
            missing.append(f)
            continue
        reason = _detect_implausible(f, value)
        if reason:
            missing.append(f)
            implausible[f] = reason
    return missing, implausible


def _rag_suggestions(
    job_title: str,
    industry: str,
    missing_fields: List[str],
    lang: str = "en",
    model: Optional[str] = None,
    vector_store_id: Optional[str] = None,
    max_items_per_field: int = 6,
) -> Dict[str, List[str]]:
    """Ask OpenAI Chat + File Search for field-specific suggestions.

    Args:
        job_title: Role title for context.
        industry: Industry for additional context.
        missing_fields: Fields to generate suggestions for.
        lang: Language code (``"en"`` or ``"de"``).
        model: Optional model override.
        vector_store_id: Optional vector store ID for retrieval. Falls back to
            ``st.session_state['vector_store_id']`` or the configured default.
        max_items_per_field: Maximum number of suggestions per field.

    Returns:
        Mapping of field name to suggestion list.
    """

    vector_store_id = vector_store_id or st.session_state.get("vector_store_id") or RAG_VECTOR_STORE_ID
    if not vector_store_id:
        st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = True
        return {}
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = False
    model = get_model_for(ModelTask.RAG_SUGGESTIONS, override=model)
    system_prompt = prompt_registry.format(
        "question_logic.rag.system",
        locale=lang,
        max_items=max_items_per_field,
    )
    user = {
        "job_title": job_title,
        "industry": industry,
        "language": lang,
        "fields": missing_fields,
        "N": max_items_per_field,
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]
    try:
        res = call_chat_api(
            messages,
            model=model,
            temperature=0,
            json_schema={
                "name": "rag_suggestions",
                "schema": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            tools=[build_file_search_tool(vector_store_id)],
            tool_choice="auto",
            task=ModelTask.RAG_SUGGESTIONS,
            verbosity=get_active_verbosity(),
        )
        data = json.loads(_normalize_chat_content(res) or "{}")
        out: Dict[str, List[str]] = {}
        for f in missing_fields:
            vals = data.get(f) or data.get(f.replace("_", " ")) or []
            sanitized = [str(x).strip() for x in vals if str(x).strip()]
            if f in SKILL_FIELDS and sanitized:
                sanitized = normalize_skills(sanitized, lang=lang)
            out[f] = sanitized
        return out
    except Exception as err:  # pragma: no cover - network/AI
        logger.warning("RAG suggestions failed: %s", err)
        try:  # pragma: no cover - UI warning
            st.warning(
                tr(
                    "Konnte keine Kontextvorschläge abrufen.",
                    "Could not retrieve contextual suggestions.",
                )
            )
        except Exception:
            pass
        return {}


def _normalize_chat_content(res: Any) -> str:
    """Extract content string from various call_chat_api responses.

    Args:
        res: Response returned by ``call_chat_api``. May be an object with a
            ``content`` attribute, a raw string, or a dictionary resembling an
            OpenAI response structure.

    Returns:
        The extracted content string or an empty string if unavailable.
    """

    if hasattr(res, "content"):
        return getattr(res, "content") or ""
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        if isinstance(res.get("content"), str):
            return res["content"]
        try:
            ch = res.get("choices", [])
            if ch:
                msg = ch[0].get("message", {})
                c = msg.get("content")
                if isinstance(c, str):
                    return c
        except Exception:
            pass
    return ""


def ask_followups(
    payload: dict,
    *,
    model: str | None = None,
    vector_store_id: Optional[str] = None,
) -> dict:
    """Generate follow-up questions via the chat API.

    Args:
        payload: Vacancy JSON payload to inspect.
        model: Optional OpenAI model identifier. Uses the globally selected
            model when ``None``.
        vector_store_id: Optional vector store ID enabling file search tool usage.
            Uses ``st.session_state['vector_store_id']`` when not provided.

    Returns:
        Parsed JSON dictionary with follow-up questions. Returns an empty dict if
        parsing fails or the response is invalid.
    """

    with tracer.start_as_current_span("llm.generate_followups") as span:
        vector_store_id = vector_store_id or st.session_state.get("vector_store_id") or RAG_VECTOR_STORE_ID
        span.set_attribute("followups.vector_store", bool(vector_store_id))
        previous_response_id = st.session_state.get(StateKeys.FOLLOWUPS_RESPONSE_ID)

        payload_lang = ""
        payload_profile: dict[str, Any] | None = None
        if isinstance(payload, dict):
            meta = payload.get("meta")
            if isinstance(meta, dict):
                payload_lang = str(meta.get("lang") or "").strip()
            if isinstance(payload.get("data"), dict):
                payload_profile = payload.get("data")
        session_lang = str(st.session_state.get("lang", "en") or "en")
        lang = (payload_lang or session_lang or "en").lower()
        if not lang.startswith("de"):
            lang = "en"
        else:
            lang = "de"
        span.set_attribute("followups.lang", lang)

        reasoning_mode = str(st.session_state.get(StateKeys.REASONING_MODE, "precise") or "precise").lower()
        mode = "fast" if reasoning_mode in {"quick", "fast", "schnell"} else "precise"
        model_config = FollowupModelConfig(model_override=model)

        try:
            plan_context = PlanContext.from_profile_and_session(
                payload_profile or payload,
                cast(Mapping[str, Any], st.session_state),
            )
            result = generate_followups_service(
                payload_profile or payload,
                mode=mode,
                locale=lang,
                model_config=model_config,
                vector_store_id=vector_store_id,
                call_llm=call_chat_api,
                build_file_search_tool=build_file_search_tool,
                previous_response_id=previous_response_id,
                plan_context=plan_context,
            )
        except Exception as exc:  # pragma: no cover - network/SDK issues
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "api_error"))
            raise

        response_id = result.get("response_id")
        st.session_state[StateKeys.FOLLOWUPS_RESPONSE_ID] = response_id
        questions = result.get("questions")
        if not isinstance(questions, list):
            span.add_event("missing_questions_array")
            return {"questions": []}

        span.set_attribute("followups.question_count", len(questions))
        return {"questions": questions}


def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: Optional[int] = None,
    lang: str = "en",
    use_rag: bool = True,
) -> List[Dict[str, Any]]:
    """Build a set of high-impact follow-up questions for missing fields."""
    job_title = str(_get_field_value(extracted, str(ProfilePaths.POSITION_JOB_TITLE), "") or "").strip()
    industry = str(_get_field_value(extracted, str(ProfilePaths.COMPANY_INDUSTRY), "") or "").strip()
    role_fields: List[str] = []
    role_questions_cfg: List[Dict[str, str]] = []
    esco_skills: List[str] = []
    esco_missing_skills: List[str] = []
    normalized_esco: List[str] = []
    existing_skill_values: Dict[str, List[str]] = {}
    for field in ESCO_ESSENTIAL_FIELDS:
        existing_skill_values[field] = sorted(_existing_value_keys(extracted, field))

    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = {}

    occupation_options = st.session_state.get(StateKeys.UI_ESCO_OCCUPATION_OPTIONS, [])
    selected_occupations = st.session_state.get(StateKeys.ESCO_SELECTED_OCCUPATIONS, []) or []
    occupation = selected_occupations[0] if selected_occupations else None
    if not occupation and occupation_options:
        occupation = occupation_options[0]
    if not occupation and job_title:
        occupation = classify_occupation(job_title, lang=lang)
        if occupation:
            occupation_options = [occupation]
            st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = occupation_options
            st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = [occupation]
    if occupation:
        candidate_role_keys = [
            canonicalize_role_key(str(occupation.get("preferredLabel") or "")),
            canonicalize_role_key(str(occupation.get("group") or "")),
        ]
        resolved_role_keys = [key for key in dict.fromkeys(candidate_role_keys) if key]
        for role_key in resolved_role_keys:
            if not role_fields:
                role_fields = list(_load_role_field_map().get(role_key, []))
            role_questions_cfg.extend(_resolve_role_questions(role_key, lang))
        source_had_skills = bool(st.session_state.get(StateKeys.ESCO_SKILLS))
        esco_skills = st.session_state.get(StateKeys.ESCO_SKILLS, [])
        if not esco_skills:
            esco_skills = get_essential_skills(occupation.get("uri", ""), lang=lang)
            if esco_skills:
                st.session_state[StateKeys.ESCO_SKILLS] = esco_skills
        if esco_skills and resolved_role_keys:
            fallback_skills = get_group_skills(occupation.get("group", ""))
            if fallback_skills and not source_had_skills:
                merged = _merge_suggestions(esco_skills, fallback_skills)
                if merged != esco_skills:
                    esco_skills = merged
                    st.session_state[StateKeys.ESCO_SKILLS] = esco_skills
    answered_fields = set(_get_followups_answered(extracted))
    fields_to_check = list(_critical_fields())
    for extra in role_fields:
        if extra not in fields_to_check:
            fields_to_check.append(extra)
    missing_fields, implausible_map = _collect_missing_fields(extracted, fields_to_check, answered=answered_fields)

    suggestions_map: Dict[str, List[str]] = {}
    if use_rag and is_llm_enabled() and missing_fields:
        suggestions_map = _rag_suggestions(
            job_title,
            industry,
            missing_fields,
            lang=lang,
            vector_store_id=st.session_state.get("vector_store_id"),
        )
    if suggestions_map:
        for key, values in list(suggestions_map.items()):
            suggestions_map[key] = _merge_suggestions(values, existing=_existing_value_keys(extracted, key))

    if esco_skills:
        normalized_lookup = normalize_skill_map(esco_skills, lang=lang)
        normalized_esco = list(normalized_lookup.values())
        st.session_state[StateKeys.ESCO_SKILLS] = normalized_esco

        esco_missing_by_field: Dict[str, List[Dict[str, str]]] = {}
        for skill_field in ESCO_SKILL_TARGET_FIELDS:
            existing_values = existing_skill_values.get(skill_field, [])
            existing_uris = _existing_esco_uris_for_field(extracted, skill_field)
            missing_for_field: List[Dict[str, str]] = []
            for key in normalized_lookup:
                label = normalized_lookup[key]
                if key in existing_values:
                    continue
                entry = _build_esco_skill_entry(label, lang)
                uri = str(entry.get("uri") or "").strip()
                if uri and uri in existing_uris:
                    continue
                missing_for_field.append(entry)
            if missing_for_field:
                esco_missing_by_field[skill_field] = missing_for_field

        st.session_state[StateKeys.ESCO_MISSING_SKILLS] = esco_missing_by_field
        esco_missing_skills = [
            entry.get("label", "")
            for entry in esco_missing_by_field.get(str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED), [])
        ]

        for skill_field in (
            str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
            str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL),
            str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
            str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL),
            str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES),
        ):
            needs_esco = skill_field in missing_fields
            seeds: List[str]
            mapped = esco_missing_by_field.get(skill_field, [])
            if mapped:
                needs_esco = True
                seeds = [entry.get("label", "") for entry in mapped if entry.get("label")]
            elif skill_field == str(ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES):
                seeds = normalized_esco
            else:
                seeds = []
            if needs_esco and seeds:
                suggestions_map[skill_field] = _merge_suggestions(
                    seeds,
                    suggestions_map.get(skill_field, []),
                    existing=set(existing_skill_values.get(skill_field, [])),
                )

    forced_questions: List[Dict[str, Any]] = []
    for esco_followup_field in ESCO_SKILL_TARGET_FIELDS:
        field_missing = list(
            (st.session_state.get(StateKeys.ESCO_MISSING_SKILLS, {}) or {}).get(esco_followup_field, [])
        )
        field_missing_labels = [entry.get("label", "") for entry in field_missing if isinstance(entry, dict)]
        if (
            field_missing_labels
            and esco_followup_field in fields_to_check
            and esco_followup_field not in missing_fields
            and esco_followup_field not in answered_fields
        ):
            forced_questions.append(
                {
                    "field": esco_followup_field,
                    "question": _question_text_for_field(esco_followup_field, lang, None),
                    "priority": _priority_for(esco_followup_field, True, None),
                    "suggestions": suggestions_map.get(esco_followup_field, []),
                }
            )

    if str(ProfilePaths.COMPENSATION_BENEFITS) in missing_fields:
        existing_keys = _existing_value_keys(extracted, str(ProfilePaths.COMPENSATION_BENEFITS))
        existing_raw = _get_field_value(extracted, str(ProfilePaths.COMPENSATION_BENEFITS), [])
        if isinstance(existing_raw, list):
            existing_text = "\n".join(str(item) for item in existing_raw if str(item).strip())
        else:
            existing_text = str(existing_raw or "")
        benefit_suggestions: List[str] = []
        if is_llm_enabled() and job_title:
            benefit_suggestions, _err, _used_fallback = get_benefit_suggestions(
                job_title,
                industry=industry,
                existing_benefits=existing_text,
                lang=lang,
            )
        if not benefit_suggestions:
            benefit_suggestions = DEFAULT_BENEFIT_SUGGESTIONS.get(lang, DEFAULT_BENEFIT_SUGGESTIONS["en"])
        suggestions_map[str(ProfilePaths.COMPENSATION_BENEFITS)] = _merge_suggestions(
            suggestions_map.get(str(ProfilePaths.COMPENSATION_BENEFITS), []),
            benefit_suggestions,
            existing=existing_keys,
        )

    questions: List[Dict[str, Any]] = []
    for cfg in role_questions_cfg:
        raw_field = cfg.get("field")
        raw_question = cfg.get("question")
        if not isinstance(raw_field, str) or not raw_field:
            continue
        if not isinstance(raw_question, str) or not raw_question:
            continue
        if raw_field in answered_fields:
            continue
        if not _is_empty(_get_field_value(extracted, raw_field, None)):
            continue
        question_text = raw_question if raw_question.endswith("?") else raw_question + "?"
        questions.append(
            {
                "field": raw_field,
                "question": question_text,
                "priority": "normal",
                "suggestions": suggestions_map.get(raw_field, []),
            }
        )

    for forced in forced_questions:
        if any(q.get("field") == forced["field"] for q in questions):
            continue
        questions.append(forced)

    for field in missing_fields:
        if any(q.get("field") == field for q in questions):
            continue
        reason = implausible_map.get(field)
        q_text = _question_text_for_field(field, lang, reason)
        priority = _priority_for(
            field,
            field == esco_followup_field and bool(esco_missing_skills),
            reason,
        )
        suggestions = suggestions_map.get(field, [])
        if field in YES_NO_FIELDS:
            prefill_value = tr("Nein", "No", lang=lang)
            question = {
                "field": field,
                "question": q_text,
                "priority": priority,
                "suggestions": suggestions,
                "prefill": prefill_value,
            }
        else:
            question = {
                "field": field,
                "question": q_text,
                "priority": priority,
                "suggestions": suggestions,
            }
        questions.append(question)

    if not questions:
        return []

    priority_order = {"critical": 0, "normal": 1, "optional": 2}
    ordered = sorted(
        enumerate(questions),
        key=lambda item: (
            priority_order.get(item[1].get("priority", "normal"), 1),
            item[0],
        ),
    )
    sorted_questions = [item[1] for item in ordered]

    if num_questions is None:
        critical_count = sum(1 for q in sorted_questions if q.get("priority") == "critical")
        normal_count = len(sorted_questions) - critical_count
        limit = critical_count + min(normal_count, 3)
        if sorted_questions:
            limit = max(limit, 1)
    else:
        limit = max(num_questions, 0)
    limit = min(limit, MAX_FOLLOWUP_QUESTIONS)
    if limit <= 0:
        return []
    return sorted_questions[:limit]
