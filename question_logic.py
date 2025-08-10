"""Logic for adaptive vacancy follow-up questions."""

from __future__ import annotations

from typing import Any, Dict, List
import json

from openai_utils import call_chat_api
from esco_utils import classify_occupation

# Extended vacancy fields to ensure a comprehensive profile
EXTENDED_FIELDS: List[str] = [
    "company_name",
    "location",
    "company_website",
    "industry",
    "company_size",
    "company_mission",
    "department",
    "team_structure",
    "reporting_line",
    "company_culture",
    "diversity_inclusion",
    "role_summary",
    "tasks",
    "responsibilities",
    "requirements",
    "experience_level",
    "education_requirements",
    "tools_technologies",
    "certifications",
    "languages_required",
    "salary_range",
    "bonus_compensation",
    "benefits",
    "health_benefits",
    "retirement_benefits",
    "learning_opportunities",
    "equity_options",
    "relocation_assistance",
    "visa_sponsorship",
    "remote_policy",
    "onsite_requirements",
    "travel_required",
    "working_hours",
    "contract_type",
    "start_date",
    "application_deadline",
    "performance_metrics",
]

# Mapping from ESCO occupation groups to additional vacancy fields that are
# relevant for those roles.
ROLE_FIELD_MAP: Dict[str, List[str]] = {
    "software developers": [
        "programming_languages",
        "frameworks",
        "tech_stack",
    ],
    "sales, marketing and public relations professionals": [
        "target_markets",
        "sales_quota",
    ],
    "nursing and midwifery professionals": [
        "required_certifications",
        "shift_schedule",
    ],
}


def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: int = 8,
    lang: str = "en",
) -> List[Dict[str, str]]:
    """Generate targeted follow-up questions for missing vacancy fields.

    The function performs a lightweight chain-of-thought reasoning step via
    the OpenAI API. It analyses the currently extracted vacancy data and
    determines which of the :data:`EXTENDED_FIELDS` are missing or unclear.
    It then asks the model to propose additional questions to fill those gaps.

    Args:
        extracted: Mapping of vacancy fields already known.
        num_questions: Maximum number of follow-up questions to return.
        lang: Language for the generated questions (``"en"`` or ``"de"``).

    Returns:
        A list of dictionaries with ``field`` and ``question`` keys.
    """

    job_title = extracted.get("job_title", "")
    occupation_info: Dict[str, str] = {}
    role_fields: List[str] = []
    if job_title:
        occupation_info = classify_occupation(job_title, lang=lang)
        group = (occupation_info.get("group") or "").lower()
        role_fields = ROLE_FIELD_MAP.get(group, [])
    fields = EXTENDED_FIELDS + role_fields
    payload = {field: extracted.get(field, "") for field in fields}
    if occupation_info:
        payload["esco_occupation"] = occupation_info.get("preferredLabel", "")
        payload["esco_group"] = occupation_info.get("group", "")
    prompt = (
        "You analyse vacancy data and ensure every field is complete. "
        "First think step-by-step about missing or vague information. "
        "Then respond with a JSON array of objects, each having 'field' and "
        f"'question'. Provide at most {num_questions} questions in {lang}. "
        "If nothing is missing, return an empty JSON array."
    )
    messages = [
        {
            "role": "system",
            "content": "You are a meticulous recruitment analyst.",
        },
        {
            "role": "user",
            "content": prompt
            + "\nCurrent data:\n"
            + json.dumps(payload, ensure_ascii=False),
        },
    ]
    response = call_chat_api(messages, temperature=0.1, max_tokens=400)
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        parsed = []
        for line in response.splitlines():
            if "?" in line:
                question = line.strip("-*0123456789. \t")
                parsed.append({"field": "", "question": question})
    result: List[Dict[str, str]] = []
    for item in parsed:
        field = item.get("field", "")
        question = item.get("question", "")
        if field or question:
            result.append({"field": field, "question": question})
    return result
