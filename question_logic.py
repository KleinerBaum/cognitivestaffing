"""Logic for adaptive vacancy follow-up questions in Vacalyzer.

This module defines the agent that analyzes extracted vacancy data and formulates additional questions 
to fill in missing details. It uses a combination of ESCO occupation data and OpenAI's Chat API to ensure 
no important field is left incomplete. 
"""

from __future__ import annotations

from typing import Any, Dict, List
import json

from openai_utils import call_chat_api
from esco_utils import classify_occupation, get_essential_skills

# Extended vacancy fields to ensure a comprehensive profile.
# These cover additional details beyond the core schema (which has ~22 fields).
EXTENDED_FIELDS: List[str] = [
    "job_title",
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

# Mapping from ESCO occupation groups to additional vacancy fields relevant for those roles.
# This allows role-specific questions (e.g., developers should be asked about programming languages).
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
    # Future occupation groups and their custom fields can be added here.
}

def generate_followup_questions(
    extracted: Dict[str, Any],
    num_questions: int = 8,
    lang: str = "en",
) -> List[Dict[str, str]]:
    """Generate targeted follow-up questions to fill missing vacancy fields.

    This function analyzes the currently extracted vacancy data and determines which additional details are needed.
    It uses a chain-of-thought prompt via OpenAI to come up with questions that ask for those missing pieces. 
    ESCO enrichment is used to tailor the questions to the role:
      - The job title is classified to an ESCO occupation (if possible), yielding a broad group.
      - Role-specific fields (from ROLE_FIELD_MAP) for that occupation group are added to the list of fields to check.
      - Essential skills for the occupation are fetched, and any not present in the extracted text are marked as missing.
    The OpenAI model is then prompted with the current data (including any ESCO-derived info) and asked to return up to 
    `num_questions` questions (in the specified language) that would help complete the profile.

    Args:
        extracted: A dictionary of currently extracted vacancy fields (some may be empty strings if not found).
        num_questions: Maximum number of follow-up questions to return.
        lang: Language code for the generated questions ("en" for English or "de" for German).

    Returns:
        A list of dictionaries, each with keys "field" and "question". 
        - "field" is the name of the field the question is asking about (it may be empty if the question doesn’t map directly to a field).
        - "question" is the text of the follow-up question to ask the user.
    """
    job_title = extracted.get("job_title", "") or ""
    occupation_info: Dict[str, str] = {}
    role_fields: List[str] = []
    essential_skills: List[str] = []
    missing_esco_skills: List[str] = []

    # 1. ESCO Occupation Classification
    if job_title:
        occupation_info = classify_occupation(job_title, lang=lang)
        group = (occupation_info.get("group") or "").lower()
        if group:
            role_fields = ROLE_FIELD_MAP.get(group, [])
        occupation_uri = occupation_info.get("uri", "")
        # 2. ESCO Essential Skills lookup
        if occupation_uri:
            essential_skills = get_essential_skills(occupation_uri, lang=lang)
            # Combine certain text fields to check which essential skills are already mentioned
            existing_text = " ".join([
                extracted.get("requirements", ""),
                extracted.get("tasks", ""),
                extracted.get("tools_technologies", ""),
            ]).lower()
            missing_esco_skills = [skill for skill in essential_skills if skill.lower() not in existing_text]

    # 3. Determine full list of fields to consider (base extended fields + any role-specific fields)
    fields_to_check = EXTENDED_FIELDS + role_fields

    # Prepare payload with current values for each field.
    payload = {field: extracted.get(field, "") for field in fields_to_check}
    # Include ESCO info in the payload for the AI’s context.
    if occupation_info:
        payload["esco_occupation"] = occupation_info.get("preferredLabel", "")
        payload["esco_group"] = occupation_info.get("group", "")
    if essential_skills:
        payload["esco_essential_skills"] = essential_skills
    if missing_esco_skills:
        # If too many missing skills, truncate to focus on the most relevant ones (to avoid overloading the prompt).
        if len(missing_esco_skills) > num_questions:
            missing_esco_skills = missing_esco_skills[:num_questions]
        payload["missing_esco_skills"] = missing_esco_skills

    # 4. Construct the prompt for OpenAI
    prompt = (
        "You analyze the given vacancy data and ensure every field is complete. "
        "First, think step-by-step about what information is missing or seems incomplete. "
        "If 'missing_esco_skills' lists some skills, make sure to ask whether the role requires those. "
        f"Then provide at most {num_questions} follow-up questions in {lang}, in JSON array format, where each element has 'field' and 'question'. "
        "Ask one question per missing item. If nothing essential is missing, return an empty JSON array."
    )
    messages = [
        {"role": "system", "content": "You are a meticulous recruitment analyst."},
        {"role": "user", "content": prompt + "\nCurrent data:\n" + json.dumps(payload, ensure_ascii=False)}
    ]

    # 5. Call OpenAI API to get the questions
    response = call_chat_api(messages, temperature=0.1, max_tokens=400)
    # Try to parse the response as JSON
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        # If the model didn't return valid JSON (it might return a list with bullets, etc.), 
        # fall back to extracting lines containing questions.
        parsed = []
        for line in response.splitlines():
            if "?" in line:
                question_text = line.strip("-*0123456789. \t")
                parsed.append({"field": "", "question": question_text})

    # 6. Post-process the questions to ensure correct structure
    result: List[Dict[str, str]] = []
    for item in parsed:
        field = item.get("field", "") or ""
        question = item.get("question", "") or ""
        if field or question:
            # Append only non-empty entries. If the model left 'field' blank for a question, we still include the question.
            result.append({"field": field, "question": question})

    return result
