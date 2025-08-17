"""Adaptive follow-up question logic with embedded ESCO + RAG.

- Classifies ``job_title`` via ESCO, fetches essential skills, and flags missing
  ones.
- Optionally queries your OpenAI Vector Store (File Search) for field-specific
  suggestions (set ``VECTOR_STORE_ID``).
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
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from openai_utils import call_chat_api

# ESCO helpers (must exist in core/esco_utils.py)
from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    normalize_skills,
)
from config import OPENAI_API_KEY

DEFAULT_LOW_COST_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
# Optional OpenAI vector store ID for RAG suggestions; set via env/secrets.
# If unset or blank, RAG lookups are skipped.
RAG_VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

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
    "requirements.hard_skills",
    "requirements.soft_skills",
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


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return len(val.strip()) == 0
    if isinstance(val, (list, tuple, set)):
        return len(val) == 0
    # Note: bool False is not "empty" for our purposes (treated as provided)
    return False


def _priority_for(field: str, is_missing_esco_skill: bool = False) -> str:
    if is_missing_esco_skill:
        return "critical"
    if field in CRITICAL_FIELDS:
        return "critical"
    return "normal"


def ask_followups(payload: dict, *, model: str = "gpt-4o-mini", vector_store_id: Optional[str] = None) -> dict:
    tools, tool_choice, extra = [], None, {}
    if vector_store_id:
        tools = [{"type": "file_search", "file_search": {"vector_store_ids": [vector_store_id]}}]
        tool_choice = "auto"
    res = call_chat_api(
        [
            {"role": "system", "content": "Return ONLY a JSON object with follow-up questions and short answer suggestions."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model=model,
        temperature=0.2,
        json_strict=True,
        tools=tools,
        tool_choice=tool_choice,
        extra=extra,
        max_tokens=800,
    )
    return json.loads(res.content or "{}")
  

def _collect_missing_fields(extracted: Dict[str, Any], fields: List[str]) -> List[str]:
    missing = []
    for f in fields:
        if _is_empty(extracted.get(f)):
            missing.append(f)
    return missing


def _rag_suggestions(
    job_title: str,
    industry: str,
    missing_fields: List[str],
    lang: str = "en",
    model: Optional[str] = None,
    vector_store_id: Optional[str] = None,
    max_items_per_field: int = 6,
) -> Dict[str, List[str]]:
    """Ask OpenAI Chat + File Search for field-specific suggestions."""

    vector_store_id = vector_store_id or RAG_VECTOR_STORE_ID
    if not vector_store_id:
        return {}
    model = model or DEFAULT_LOW_COST_MODEL
    sys = (
        "You provide short, concrete suggestions to help complete a vacancy profile. "
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
        answer = call_chat_api(
            messages,
            model=model,
            temperature=0,
            json_strict=True,
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
        )
        data = json.loads(answer or "{}")
        out: Dict[str, List[str]] = {}
        for f in missing_fields:
            vals = data.get(f) or data.get(f.replace("_", " ")) or []
            sanitized = [str(x).strip() for x in vals if str(x).strip()]
            if f in SKILL_FIELDS and sanitized:
                sanitized = normalize_skills(sanitized, lang=lang)
            out[f] = sanitized
        return out
    except Exception:
        return {}


def _normalize_chat_content(res: Any) -> str:
    """
    Akzeptiert beliebige call_chat_api-Rückgaben und extrahiert den Textinhalt:
    - ChatCallResult-ähnlich (mit .content)
    - Raw-String
    - Raw-Dict (z. B. openai-py response mit choices[0].message.content)
    """
    # 1) bevorzugt: Dataclass/Objekt mit .content
    if hasattr(res, "content"):
        return getattr(res, "content") or ""

    # 2) reiner String
    if isinstance(res, str):
        return res

    # 3) Dict-ähnlich: verschiedene Formen abdecken
    if isinstance(res, dict):
        # a) direkte 'content'-Key
        if "content" in res and isinstance(res["content"], str):
            return res["content"]

        # b) OpenAI-ähnliche Struktur: choices[0].message.content
        try:
            choices = res.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"] or ""
        except Exception:
            pass

    # Fallback
    return ""

def ask_followups(payload: dict, *, model: str = "gpt-4o-mini", vector_store_id: Optional[str] = None) -> dict:
    tools, tool_choice, extra = [], None, {}
    if vector_store_id:
        # Hinweis: Nur aktivieren, wenn deine call_chat_api/Backend diese Tool-Form unterstützt
        tools = [{"type": "file_search", "file_search": {"vector_store_ids": [vector_store_id]}}]
        tool_choice = "auto"

    res = call_chat_api(
        [
            {"role": "system", "content": "Return ONLY a JSON object with follow-up questions and short answer suggestions."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model=model,
        temperature=0.2,
        json_strict=True,
        tools=tools or None,
        tool_choice=tool_choice,
        extra=extra,
        max_tokens=800,
    )

    content = _normalize_chat_content(res).strip()

    # Defensive: Falls der Provider trotz json_strict Codefences zurückgibt
    if content.startswith("```"):
        import re
        m = re.search(r"```(?:json)?\s*(.*?)```", content, re.S | re.I)
        if m:
            content = m.group(1).strip()

    try:
        return json.loads(content or "{}")
    except json.JSONDecodeError:
        # Hard fallback: leeres Objekt statt Exception (UI bleibt stabil)
        return {}
      
  
def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: Optional[int] = None,
    lang: str = "en",
    use_rag: bool = True,
) -> List[Dict[str, Any]]:
    """Build a set of high-impact follow-up questions for missing fields."""
    # 1) Determine role-specific fields via ESCO classification
    job_title = (extracted.get("position.job_title") or "").strip()
    industry = (extracted.get("company.industry") or "").strip()
    occupation = {}
    essential_skills: List[str] = []
    missing_esco_skills: List[str] = []
    occ_group = ""
    role_questions_cfg: List[Dict[str, str]] = []
    if job_title:
        occupation = classify_occupation(job_title, lang=lang) or {}
        occ_group = (occupation.get("group") or "").lower()
        role_fields = ROLE_FIELD_MAP.get(occ_group, [])
        role_questions_cfg = ROLE_QUESTION_MAP.get(occ_group, [])
    else:
        role_fields = []
        role_questions_cfg = []
    occ_uri = occupation.get("uri", "")
    if occ_uri:
        essential_skills = get_essential_skills(occ_uri, lang=lang) or []
        # Check which essential skills are not mentioned in any provided skills/requirements text
        haystack_text = " ".join(
            [
                str(extracted.get("responsibilities.items") or ""),
                str(extracted.get("position.role_summary") or ""),
                str(extracted.get("requirements.hard_skills") or ""),
                str(extracted.get("requirements.soft_skills") or ""),
                str(extracted.get("requirements.tools_and_technologies") or ""),
            ]
        ).lower()
        missing_esco_skills = [
            s for s in essential_skills if s.lower() not in haystack_text
        ]
    # 2) Determine which fields are missing
    fields_to_check = list(CRITICAL_FIELDS)  # start with critical fields
    # Include role-specific extra fields for this occupation group (not marked critical but should ask if missing)
    for extra in role_fields:
        if extra not in fields_to_check:
            fields_to_check.append(extra)
    missing_fields = _collect_missing_fields(extracted, fields_to_check)
    # If salary fields are missing but salary_provided is True, combine as one "salary" question
    if (
        "compensation.salary_min" in missing_fields
        and "compensation.salary_max" in missing_fields
    ):
        # Remove individual salary fields and ask one question covering both
        missing_fields = [
            f for f in missing_fields if not f.startswith("compensation.salary_")
        ]
        missing_fields.append("compensation.salary_range")
    # Compute number of questions if not explicitly given
    if num_questions is None:
        critical_missing = [f for f in missing_fields if f in CRITICAL_FIELDS]
        optional_missing = [f for f in missing_fields if f not in CRITICAL_FIELDS]
        base_num = len(critical_missing) + min(len(optional_missing), 3)
        num_questions = min(max(base_num, 3), 12)
        num_questions += len(role_questions_cfg)  # include predefined role-specific Qs
    # 3) (Optional) Get suggestions via RAG for missing fields
    suggestions_map: Dict[str, List[str]] = {}
    if use_rag and use_rag and (OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")):
        try:
            suggestions_map = _rag_suggestions(
                job_title, industry, missing_fields, lang=lang
            )
        except Exception:
            suggestions_map = {}
    # 4) Construct question payloads
    questions: List[Dict[str, Any]] = []
    # Predefined role-specific questions (from ROLE_QUESTION_MAP)
    for cfg in role_questions_cfg:
        field = cfg.get("field")
        q_text = cfg.get("question")
        if field and q_text and _is_empty(extracted.get(field, None)):
            questions.append(
                {
                    "field": field,
                    "question": q_text + ("?" if not q_text.endswith("?") else ""),
                    "priority": "normal",
                    "suggestions": suggestions_map.get(field, []),
                }
            )
    # Questions for each missing field
    for field in missing_fields:
        # Skip if already added via role_questions_cfg
        if any(q.get("field") == field for q in questions):
            continue
        # Determine field-specific prompt text
        if field == "compensation.salary_range":
            q_text = (
                "What is the salary range (min and max) and currency for this position?"
            )
        elif field.startswith("responsibilities."):
            q_text = "Could you list the key responsibilities or tasks for this role?"  # covers responsibilities.items
        elif field.startswith("requirements.hard_skills"):
            q_text = "What hard skills or technical competencies are required?"
        elif field.startswith("requirements.soft_skills"):
            q_text = "What soft skills or interpersonal skills are important?"
        elif field.startswith("requirements.tools_and_technologies"):
            q_text = (
                "Which tools and technologies should the candidate be familiar with?"
            )
        elif field == "requirements.language_level_english":
            q_text = "What English proficiency level is required (e.g., B2, C1)?"
        elif field == "location.primary_city":
            q_text = "In which city is this position based?"
        elif field == "location.country":
            q_text = "In which country is this position located?"
        else:
            # Default question format
            label = field.split(".")[-1].replace("_", " ")
            q_text = (
                f"Please provide the {label}."
                if lang != "de"
                else f"Bitte geben Sie {label} an."
            )
        priority = _priority_for(field, field in missing_esco_skills)
        suggestions = suggestions_map.get(field, [])
        prefill = None
        if field in YES_NO_FIELDS:
            prefill = (
                "No"  # default to "No" if not specified (to prompt user to confirm)
            )
        questions.append(
            {
                "field": field,
                "question": (q_text if q_text.endswith("?") else q_text + "?"),
                "priority": priority,
                "suggestions": suggestions,
                **({"prefill": prefill} if prefill is not None else {}),
            }
        )
    # Sort questions by priority (critical first) and limit to num_questions
    sorted_questions = sorted(
        questions, key=lambda q: 0 if q["priority"] == "critical" else 1
    )
    return sorted_questions[:num_questions]
