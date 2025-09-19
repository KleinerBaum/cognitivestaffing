"""Adaptive follow-up question logic with optional RAG enrichment.

- ESCO-based occupation and skill lookups are disabled; only RAG suggestions
  contribute additional context.
- Asks the LLM to produce compact, localized questions with priority flags and
  options.

Outputs (for UI sorting and chips):
[
  {
    "field": "salary_range",
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
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import streamlit as st
from openai_utils import call_chat_api
from utils.i18n import tr

# ESCO helpers (core utils + offline-aware wrapper)
from core.esco_utils import normalize_skills
from core.suggestions import get_benefit_suggestions
from config import OPENAI_API_KEY, VECTOR_STORE_ID, ModelTask, get_model_for

# Optional OpenAI vector store ID for RAG suggestions; set via env/secrets.
# If unset or blank, RAG lookups are skipped.
RAG_VECTOR_STORE_ID = VECTOR_STORE_ID

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
with open(_ROOT / "critical_fields.json", "r", encoding="utf-8") as _f:
    CRITICAL_FIELDS: Set[str] = set(json.load(_f).get("critical", []))
with open(_ROOT / "role_field_map.json", "r", encoding="utf-8") as _f:
    ROLE_FIELD_MAP: Dict[str, List[str]] = {
        k.lower(): v for k, v in json.load(_f).items()
    }

# Predefined role-specific follow-up questions keyed by ESCO group (lowercased)
ROLE_QUESTION_MAP: Dict[str, List[Dict[str, str]]] = {
    "software developers": [
        {
            "field": "programming_languages",
            "question": "Which programming languages will the developer use?",
        },
        {
            "field": "development_methodology",
            "question": "Which development methodology does the team follow?",
        },
    ],
    "sales, marketing and public relations professionals": [
        {
            "field": "target_markets",
            "question": "Which target markets will the salesperson focus on?",
        },
        {
            "field": "sales_quota",
            "question": "What is the sales quota for this role?",
        },
        {
            "field": "campaign_types",
            "question": "What campaign types will the marketer manage?",
        },
        {
            "field": "digital_marketing_platforms",
            "question": "Which digital marketing platforms are used?",
        },
    ],
    "nursing and midwifery professionals": [
        {
            "field": "shift_schedule",
            "question": "What is the shift schedule?",
        },
    ],
    "medical doctors": [
        {
            "field": "board_certification",
            "question": "What board certifications are required?",
        },
        {
            "field": "on_call_requirements",
            "question": "Are there on-call requirements for this role?",
        },
    ],
    "teaching professionals": [
        {
            "field": "grade_level",
            "question": "Which grade levels will the teacher instruct?",
        },
        {
            "field": "teaching_license",
            "question": "Is a teaching license required?",
        },
    ],
    "graphic and multimedia designers": [
        {
            "field": "design_software_tools",
            "question": "Which design software tools should the designer be proficient in?",
        },
        {
            "field": "portfolio_url",
            "question": "What is the portfolio URL?",
        },
    ],
    "business services and administration managers not elsewhere classified": [
        {
            "field": "project_management_methodologies",
            "question": "Which project management methodologies are used?",
        },
        {
            "field": "budget_responsibility",
            "question": "What budget responsibility does this role carry?",
        },
    ],
    "systems analysts": [
        {
            "field": "machine_learning_frameworks",
            "question": "Which machine learning frameworks are required?",
        },
        {
            "field": "data_analysis_tools",
            "question": "Which data analysis tools are used?",
        },
    ],
    "accountants": [
        {
            "field": "accounting_software",
            "question": "Which accounting software is used?",
        },
        {
            "field": "professional_certifications",
            "question": "Which professional certifications are required?",
        },
    ],
    "human resource professionals": [
        {
            "field": "hr_software_tools",
            "question": "Which HR software tools are used?",
        },
        {
            "field": "recruitment_channels",
            "question": "Which recruitment channels are prioritized?",
        },
    ],
    "civil engineers": [
        {
            "field": "civil_project_types",
            "question": "What types of civil projects will the engineer handle?",
        },
        {
            "field": "engineering_software_tools",
            "question": "Which engineering software tools are required?",
        },
    ],
    "chefs": [
        {
            "field": "cuisine_specialties",
            "question": "Which cuisine specialties should the chef have?",
        },
    ],
}

SKILL_FIELDS: Set[str] = {
    "requirements.hard_skills_required",
    "requirements.hard_skills_optional",
    "requirements.soft_skills_required",
    "requirements.soft_skills_optional",
    "requirements.tools_and_technologies",
}

YES_NO_FIELDS: Set[str] = {
    "compensation.variable_pay",
    "compensation.equity_offered",
    "employment.travel_required",
    "employment.overtime_expected",
    "employment.relocation_support",
    "employment.security_clearance_required",
    "employment.shift_work",
    "employment.visa_sponsorship",
    "requirements.background_check_required",
    "requirements.portfolio_required",
    "requirements.reference_check_required",
}

PLACEHOLDER_STRINGS: Set[str] = {
    "tbd",
    "to be defined",
    "n/a",
    "na",
    "keine",
    "kein",
    "none",
    "unknown",
    "?",
    "-",
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


def _normalize_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return str(value).strip().lower()


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
            normalized.add(text.lower())
    return normalized


def _merge_suggestions(
    *iterables: Iterable[str], existing: Optional[Set[str]] = None
) -> List[str]:
    seen = set(existing or set())
    merged: List[str] = []
    for iterable in iterables:
        for item in iterable or []:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
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


def _is_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return _normalize_str(value) in PLACEHOLDER_STRINGS
    return False


def _detect_implausible(field: str, value: Any) -> Optional[Tuple[str, Any]]:
    if _is_empty(value):
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value if str(v).strip()]
        if items and all(_is_placeholder(v) for v in items):
            return ("placeholder", items)
        return None
    if isinstance(value, str) and _is_placeholder(value):
        return ("placeholder", value)
    if field.startswith("compensation.salary"):
        numeric = _coerce_to_float(value)
        if numeric is not None and numeric <= 0:
            return ("salary_unrealistic", numeric)
    return None


def _question_text_for_field(
    field: str, lang: str, reason: Optional[Tuple[str, Any]]
) -> str:
    label = field.split(".")[-1].replace("_", " ")
    if field == "compensation.salary_range":
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
    elif field.startswith("requirements.hard_skills"):
        base = tr(
            "Welche Hard Skills oder technischen Kompetenzen werden benötigt?",
            "What hard skills or technical competencies are required?",
            lang=lang,
        )
    elif field.startswith("requirements.soft_skills"):
        base = tr(
            "Welche Soft Skills oder zwischenmenschlichen Fähigkeiten sind wichtig?",
            "What soft skills or interpersonal skills are important?",
            lang=lang,
        )
    elif field.startswith("requirements.tools_and_technologies"):
        base = tr(
            "Mit welchen Tools und Technologien sollte der Kandidat vertraut sein?",
            "Which tools and technologies should the candidate be familiar with?",
            lang=lang,
        )
    elif field == "requirements.language_level_english":
        base = tr(
            "Welches Englischniveau wird benötigt (z. B. B2, C1)?",
            "What English proficiency level is required (e.g., B2, C1)?",
            lang=lang,
        )
    elif field == "location.primary_city":
        base = tr(
            "In welcher Stadt ist die Position angesiedelt?",
            "In which city is this position based?",
            lang=lang,
        )
    elif field == "location.country":
        base = tr(
            "In welchem Land ist die Position angesiedelt?",
            "In which country is this position located?",
            lang=lang,
        )
    elif field == "compensation.benefits":
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
    if reason and reason[0] == "placeholder" and field != "compensation.salary_range":
        base = tr(
            "Die aktuelle Angabe wirkt wie ein Platzhalter. Bitte ergänzen Sie {label}.",
            "The current entry looks like a placeholder. Please provide the {label}.",
            lang=lang,
        ).format(label=label)
    return base if base.endswith("?") else base + "?"


def _get_followups_answered(extracted: Dict[str, Any]) -> List[str]:
    raw = _get_field_value(extracted, "meta.followups_answered", [])
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
    if field in CRITICAL_FIELDS:
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

    vector_store_id = (
        vector_store_id
        or st.session_state.get("vector_store_id")
        or RAG_VECTOR_STORE_ID
    )
    if not vector_store_id:
        return {}
    model = get_model_for(ModelTask.RAG_SUGGESTIONS, override=model)
    sys = (
        "You provide short, concrete suggestions to help complete a profile. "
        "Use retrieved context; if none, return empty arrays. Respond as a JSON object "
        "mapping each requested field to an array of up to N concise suggestions (no explanations)."
    )
    user = {
        "job_title": job_title,
        "industry": industry,
        "language": lang,
        "fields": missing_fields,
        "N": max_items_per_field,
    }
    messages = [
        {"role": "system", "content": sys},
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
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
            tool_choice="auto",
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

    model = get_model_for(ModelTask.FOLLOW_UP_QUESTIONS, override=model)
    vector_store_id = (
        vector_store_id
        or st.session_state.get("vector_store_id")
        or RAG_VECTOR_STORE_ID
    )
    tools: list[Any] = []
    tool_choice: Optional[str] = None
    if vector_store_id:
        tools = [{"type": "file_search", "vector_store_ids": [vector_store_id]}]
        tool_choice = "auto"

    res = call_chat_api(
        [
            {
                "role": "system",
                "content": "Return ONLY a JSON object with follow-up questions and short answer suggestions.",
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model=model,
        temperature=0.2,
        json_schema={
            "name": "followup_questions",
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "question": {"type": "string"},
                                "priority": {"type": "string"},
                                "suggestions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "default": [],
                                },
                            },
                            "required": [
                                "field",
                                "question",
                                "priority",
                                "suggestions",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["questions"],
                "additionalProperties": False,
            },
        },
        tools=tools or None,
        tool_choice=tool_choice,
        max_tokens=800,
    )

    content = _normalize_chat_content(res).strip()
    if content.startswith("```"):
        import re

        m = re.search(r"```(?:json)?\s*(.*?)```", content, re.S | re.I)
        if m:
            content = m.group(1).strip()
    try:
        parsed = json.loads(content or "{}")
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    questions = parsed.get("questions")
    if not isinstance(questions, list):
        parsed["questions"] = []
        return parsed

    normalized_questions: List[Dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        suggestions = normalized.get("suggestions")
        if isinstance(suggestions, list):
            normalized["suggestions"] = [
                str(s) for s in suggestions if isinstance(s, str)
            ]
        else:
            normalized["suggestions"] = []
        normalized_questions.append(normalized)

    parsed["questions"] = normalized_questions
    return parsed


def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: Optional[int] = None,
    lang: str = "en",
    use_rag: bool = True,
) -> List[Dict[str, Any]]:
    """Build a set of high-impact follow-up questions for missing fields."""
    job_title = str(_get_field_value(extracted, "position.job_title", "") or "").strip()
    industry = str(_get_field_value(extracted, "company.industry", "") or "").strip()
    role_fields: List[str] = []
    role_questions_cfg: List[Dict[str, str]] = []
    answered_fields = set(_get_followups_answered(extracted))
    fields_to_check = list(CRITICAL_FIELDS)
    for extra in role_fields:
        if extra not in fields_to_check:
            fields_to_check.append(extra)
    missing_fields, implausible_map = _collect_missing_fields(
        extracted, fields_to_check, answered=answered_fields
    )

    if (
        "compensation.salary_min" in missing_fields
        and "compensation.salary_max" in missing_fields
    ):
        missing_fields = [
            f for f in missing_fields if not f.startswith("compensation.salary_")
        ]
        combined_reason = implausible_map.pop(
            "compensation.salary_min", None
        ) or implausible_map.pop("compensation.salary_max", None)
        missing_fields.append("compensation.salary_range")
        if combined_reason:
            implausible_map["compensation.salary_range"] = combined_reason

    suggestions_map: Dict[str, List[str]] = {}
    if use_rag and OPENAI_API_KEY and missing_fields:
        suggestions_map = _rag_suggestions(
            job_title,
            industry,
            missing_fields,
            lang=lang,
            vector_store_id=st.session_state.get("vector_store_id"),
        )
    if suggestions_map:
        for key, values in list(suggestions_map.items()):
            suggestions_map[key] = _merge_suggestions(
                values, existing=_existing_value_keys(extracted, key)
            )

    if "compensation.benefits" in missing_fields:
        existing_keys = _existing_value_keys(extracted, "compensation.benefits")
        existing_raw = _get_field_value(extracted, "compensation.benefits", [])
        if isinstance(existing_raw, list):
            existing_text = "\n".join(
                str(item) for item in existing_raw if str(item).strip()
            )
        else:
            existing_text = str(existing_raw or "")
        benefit_suggestions: List[str] = []
        if OPENAI_API_KEY and job_title:
            benefit_suggestions, _err = get_benefit_suggestions(
                job_title,
                industry=industry,
                existing_benefits=existing_text,
                lang=lang,
            )
        if not benefit_suggestions:
            benefit_suggestions = DEFAULT_BENEFIT_SUGGESTIONS.get(
                lang, DEFAULT_BENEFIT_SUGGESTIONS["en"]
            )
        suggestions_map["compensation.benefits"] = _merge_suggestions(
            suggestions_map.get("compensation.benefits", []),
            benefit_suggestions,
            existing=existing_keys,
        )

    questions: List[Dict[str, Any]] = []
    for cfg in role_questions_cfg:
        field = cfg.get("field")
        q_text = cfg.get("question")
        if not field or not q_text or field in answered_fields:
            continue
        if not _is_empty(_get_field_value(extracted, field, None)):
            continue
        questions.append(
            {
                "field": field,
                "question": q_text if q_text.endswith("?") else q_text + "?",
                "priority": "normal",
                "suggestions": suggestions_map.get(field, []),
            }
        )

    for field in missing_fields:
        if any(q.get("field") == field for q in questions):
            continue
        reason = implausible_map.get(field)
        q_text = _question_text_for_field(field, lang, reason)
        priority = _priority_for(
            field,
            False,
            reason,
        )
        suggestions = suggestions_map.get(field, [])
        if field in YES_NO_FIELDS:
            prefill_value = "Nein" if lang == "de" else "No"
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
        critical_count = sum(
            1 for q in sorted_questions if q.get("priority") == "critical"
        )
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
