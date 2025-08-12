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
from typing import Any, Dict, List, Optional, Set

# ESCO helpers (must exist in core/esco_utils.py)


from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    normalize_skills,
)

# Generic chat helper (fallback)
from openai_utils import call_chat_api
from config import OPENAI_API_KEY

# Try modern OpenAI SDK (Responses API)
try:
    from openai import OpenAI  # >=1.30

    _HAS_RESPONSES = True
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment, misc]
    _HAS_RESPONSES = False

DEFAULT_LOW_COST_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Optional OpenAI vector store ID for RAG suggestions; set via env/secrets.
# If unset or blank, RAG lookups are skipped.
RAG_VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "").strip()

# Extended coverage: combine legacy and new fields (kept flat for prompts).
EXTENDED_FIELDS: List[str] = [
    # company / context
    "company_name",
    "company_website",
    "industry",
    "location",
    "company_mission",
    "company_culture",
    "department",
    "team_structure",
    "reporting_line",
    # role core
    "job_title",
    "role_summary",
    "responsibilities",
    "qualifications",
    "hard_skills",
    "soft_skills",
    "tools_and_technologies",
    "certifications",
    "languages_required",
    "seniority_level",
    # employment
    "job_type",
    "remote_policy",
    "onsite_requirements",
    "travel_required",
    "working_hours",
    "salary_range",
    "bonus_compensation",
    "benefits",
    "health_benefits",
    "retirement_benefits",
    "learning_opportunities",
    "equity_options",
    "relocation_assistance",
    "visa_sponsorship",
    "target_start_date",
    "application_deadline",
    "performance_metrics",
]

# Role-specific extras keyed by ESCO group (lowercased)
ROLE_FIELD_MAP: Dict[str, List[str]] = {
    "software developers": [
        "programming_languages",
        "frameworks",
        "tech_stack",
        "code_quality_practices",
    ],
    "sales, marketing and public relations professionals": [
        "target_markets",
        "sales_quota",
        "crm_tools",
    ],
    "nursing and midwifery professionals": [
        "required_certifications",
        "shift_schedule",
        "patient_ratio",
    ],
}

CRITICAL_FIELDS: Set[str] = {
    "job_title",
    "company_name",
    "location",
    "role_summary",
    "responsibilities",
    "qualifications",
    "salary_range",
    "job_type",
    "remote_policy",
    "languages_required",
    "certifications",
    "tools_and_technologies",
}


SKILL_FIELDS: Set[str] = {"hard_skills", "soft_skills", "tools_and_technologies"}

# Fields that typically represent yes/no questions. These will receive a
# default prefill of "Not specified" if no better hint is available.
YES_NO_FIELDS: Set[str] = {
    "bonus_compensation",
    "health_benefits",
    "retirement_benefits",
    "learning_opportunities",
    "equity_options",
    "relocation_assistance",
    "visa_sponsorship",
}


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return len(val.strip()) == 0
    if isinstance(val, (list, tuple, set)):
        return len(val) == 0
    return False


def _priority_for(field: str, is_missing_esco_skill: bool = False) -> str:
    if is_missing_esco_skill:
        return "critical"
    if field in CRITICAL_FIELDS:
        return "critical"
    # Favor role-relevant extras as normal
    return "normal"


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
    """Ask OpenAI Responses + File Search for field-specific suggestions.

    Returns a mapping ``field -> [suggestion, ...]``. If ``vector_store_id`` is
    ``None`` or blank, no lookup is performed and an empty dict is returned.
    """
    if not _HAS_RESPONSES:
        return {}  # fallback handled later
    vector_store_id = vector_store_id or RAG_VECTOR_STORE_ID
    if not vector_store_id:
        return {}
    client = OpenAI()
    model = model or DEFAULT_LOW_COST_MODEL

    # Keep it deterministic and cheap; ask for JSON only.
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
    try:
        resp = client.responses.create(  # type: ignore[call-overload]
            model=model,
            input=[
                {"role": "system", "content": sys},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        # Modern SDK helper
        text = getattr(resp, "output_text", None)
        if not text:
            # Fallback: build string from first text output
            # (robust to SDK variants)
            text = ""
            if hasattr(resp, "output") and isinstance(resp.output, list):
                for node in resp.output:
                    if "content" in node and node["content"]:
                        for seg in node["content"]:
                            if seg.get("type") == "output_text":
                                text += seg.get("text", "")
        data = json.loads(text or "{}")
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


def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: Optional[int] = None,
    lang: str = "en",
    use_rag: bool = True,
) -> List[Dict[str, Any]]:
    """Build a small set of high-impact follow-up questions.

    If ``num_questions`` is ``None``, the amount of questions is derived from
    the importance of the missing fields. Critical fields are prioritised and
    may be split into sub-questions (e.g. ``qualifications`` yields separate
    education and experience prompts). The total defaults to between three and
    seven questions. Each item contains the target field, the localized
    question, a priority flag, optional suggestions, and a ``prefill`` hint
    used to prime the answer field in the UI.

    Returns: list of {field, question, priority, suggestions?, prefill?}
    """
    # 1) ESCO occupation + essential skills
    job_title = (extracted.get("job_title") or "").strip()
    industry = (extracted.get("industry") or "").strip()
    occupation = {}
    essential_skills: List[str] = []
    missing_esco_skills: List[str] = []

    if job_title:
        occupation = classify_occupation(job_title, lang=lang) or {}
        occ_group = (occupation.get("group") or "").lower()
        role_fields = ROLE_FIELD_MAP.get(occ_group, [])
    else:
        role_fields = []

    occ_uri = occupation.get("uri", "")
    if occ_uri:
        essential_skills = get_essential_skills(occ_uri, lang=lang) or []
        # text presence check
        haystack = " ".join(
            [
                str(extracted.get("responsibilities") or ""),
                str(extracted.get("qualifications") or ""),
                str(extracted.get("hard_skills") or ""),
                str(extracted.get("soft_skills") or ""),
                str(extracted.get("tools_and_technologies") or ""),
            ]
        ).lower()
        missing_esco_skills = [s for s in essential_skills if s.lower() not in haystack]

    # 2) Missing fields
    fields_to_check = list(
        dict.fromkeys(EXTENDED_FIELDS + role_fields)
    )  # dedupe keep order
    missing_fields = _collect_missing_fields(extracted, fields_to_check)

    if not missing_fields and not missing_esco_skills:
        return []

    if num_questions is None:
        critical_missing = [f for f in missing_fields if f in CRITICAL_FIELDS]
        optional_missing = [f for f in missing_fields if f not in CRITICAL_FIELDS]
        base = len(critical_missing) + min(len(optional_missing), 3)
        if "qualifications" in critical_missing:
            base += 1
        num_questions = min(max(base, 3), 7)

    split_fields: Dict[str, List[str]] = {}
    if "qualifications" in missing_fields:
        split_fields["qualifications"] = ["education", "experience"]

    # 3) RAG suggestions (chips)
    rag_map: Dict[str, List[str]] = {}
    if use_rag and missing_fields:
        rag_map = _rag_suggestions(job_title, industry, missing_fields, lang=lang)

    # 4) Build LLM prompt with context (ask LLM to phrase questions & attach priority + suggestions)
    payload = {
        "current": {k: extracted.get(k, "") for k in fields_to_check},
        "language": lang,
        "missing_fields": missing_fields,
        "occupation": occupation,
        "essential_skills": essential_skills[:24],  # budget cap
        "missing_esco_skills": missing_esco_skills[:12],  # budget cap
        "rag_suggestions": rag_map,  # may be empty
        "rules": {
            "max_questions": num_questions,
            "priorities": {
                "critical_fields": sorted(list(CRITICAL_FIELDS)),
                "isco_group_fields": role_fields,
            },
            **({"split_fields": split_fields} if split_fields else {}),
            "format": {
                "type": "array",
                "item": {
                    "field": "str",
                    "question": "str",
                    "priority": "critical|normal|optional",
                    "suggestions?": "list[str]",
                },
            },
            "language": lang,
        },
    }

    # instruction in target language
    if lang == "de":
        instruction = (
            "Analysiere die Felder. Formuliere bis zu N gezielte Nachfragen. "
            "Kennzeichne jede Frage mit 'priority' (critical/normal/optional). "
            "Falls 'missing_esco_skills' vorhanden sind, frage nach diesen gezielt. "
            "Wenn 'rag_suggestions' Einträge für ein Feld enthält, füge sie als 'suggestions' (Array) bei. "
            "Antworte NUR als JSON-Array der Objekte {field, question, priority, suggestions?}."
        )
    else:
        instruction = (
            "Review the fields. Ask up to N targeted questions. "
            "Mark each with 'priority' (critical/normal/optional). "
            "If 'missing_esco_skills' exist, include explicit questions for them. "
            "If 'rag_suggestions' has entries for a field, include them as 'suggestions' (array). "
            "Respond ONLY as a JSON array of {field, question, priority, suggestions?}."
        )

    user_msg = {
        "N": num_questions,
        "context": payload,
        "instruction": instruction,
    }

    # Prefer modern Responses+JSON if available (cheaper parsing); fallback to Chat
    if _HAS_RESPONSES and OPENAI_API_KEY:
        try:
            client = OpenAI()
            resp = client.responses.create(  # type: ignore[call-overload]
                model=DEFAULT_LOW_COST_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": "You are a meticulous recruitment analyst.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_msg, ensure_ascii=False),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            text = getattr(resp, "output_text", None) or "{}"
            data = json.loads(text)
            items = (
                data
                if isinstance(data, list)
                else data.get("items") or data.get("questions") or []
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}") from e
    else:
        # Chat fallback
        chat_prompt = f"{instruction}\nN={num_questions}\n\nContext:\n{json.dumps(payload, ensure_ascii=False)}"
        try:
            raw = call_chat_api(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a meticulous recruitment analyst.",
                    },
                    {"role": "user", "content": chat_prompt},
                ],
                temperature=0.1,
                max_tokens=600,
            )
        except Exception as e:  # pragma: no cover - network failure
            raise RuntimeError(f"OpenAI API error: {e}") from e
        try:
            items = json.loads(raw)
        except Exception:
            # ultra-fallback: heuristics from lines with '?'
            items = []
            for line in raw.splitlines():
                if "?" in line:
                    items.append(
                        {
                            "field": "",
                            "question": line.strip("-*• 0123456789.\t "),
                            "priority": "normal",
                        }
                    )

    # 5) Post-process: default priorities, attach suggestions, cap length
    out: List[Dict[str, Any]] = []
    esco_set = {s.lower() for s in missing_esco_skills}
    for it in items:
        field = str(it.get("field", "") or "")
        q = str(it.get("question", "") or "")
        pr = str(it.get("priority", "") or "").lower()
        sugg = it.get("suggestions") or []
        prefill = str(it.get("prefill", "") or "")

        # Default / fixup priority
        if pr not in {"critical", "normal", "optional"}:
            pr = _priority_for(
                field,
                is_missing_esco_skill=(
                    q.lower() in esco_set or field in {"hard_skills", "qualifications"}
                ),
            )

        # Merge RAG suggestions if field present and none attached
        if field and not sugg and rag_map.get(field):
            sugg = rag_map[field][:6]

        # Use first suggestion as prefill if none provided
        if field and not prefill and rag_map.get(field):
            prefill = rag_map[field][0]

        # Default prefill for yes/no style questions
        if field in YES_NO_FIELDS and not prefill:
            prefill = "Not specified"

        if field or q:
            out.append(
                {
                    "field": field,
                    "question": q,
                    "priority": pr,
                    "suggestions": sugg,
                    "prefill": prefill,
                }
            )

    # Sort: critical → normal → optional, keep original order within tier; cap N
    rank = {"critical": 0, "normal": 1, "optional": 2}
    out.sort(key=lambda x: rank.get(x["priority"], 1))
    return out[:num_questions]
