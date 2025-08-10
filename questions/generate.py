"""Generate follow-up questions for incomplete job descriptions."""

from __future__ import annotations

import json
from typing import List

from core.schema import ALL_FIELDS, VacalyserJD
from esco_utils import classify_occupation, get_essential_skills
from openai_utils import call_chat_api

from .missing import missing_fields


def generate_followup_questions(jd: VacalyserJD, lang: str = "en") -> List[str]:
    """Return targeted questions for missing fields in ``jd``.

    The function inspects the job description and asks the LLM for
    clarifications only for fields that are currently empty. Between three
    and seven questions are requested. If no fields are missing, an empty
    list is returned. Additionally, if ``responsibilities`` or ``hard_skills``
    are empty but ESCO lists essential skills for the role, one probing
    question for each category is appended.

    Args:
        jd: Parsed job description data.
        lang: Language for generated questions.

    Returns:
        List of follow-up question strings.
    """

    missing = missing_fields(jd)
    if not missing:
        return []

    extras: List[str] = []
    if jd.job_title and {"responsibilities", "hard_skills"} & set(missing):
        occ = classify_occupation(jd.job_title, lang=lang)
        uri = occ.get("uri", "")
        essential = get_essential_skills(uri, lang=lang) if uri else []
        if "responsibilities" in missing and essential:
            extras.append("What are the main responsibilities for this role?")
            missing.remove("responsibilities")
        if "hard_skills" in missing and essential:
            sample = ", ".join(essential[:3])
            extras.append(
                f"Does the role require any of the following skills: {sample}?"
            )
            missing.remove("hard_skills")

    if not missing:
        return extras

    num_questions = min(max(len(missing), 3), 7)
    payload = {field: getattr(jd, field) for field in ALL_FIELDS}
    prompt = (
        "You ensure vacancy data is complete. "
        f"Ask {num_questions} concise questions in {lang} to fill the missing "
        f"fields: {', '.join(missing)}. Return a JSON array of strings."
    )
    messages = [
        {"role": "system", "content": "You are a meticulous recruitment analyst."},
        {
            "role": "user",
            "content": prompt + "\nData:\n" + json.dumps(payload, ensure_ascii=False),
        },
    ]
    response = call_chat_api(messages, temperature=0.1, max_tokens=400)
    try:
        questions = json.loads(response)
    except json.JSONDecodeError:
        questions = [
            line.strip("-*0123456789. \t")
            for line in response.splitlines()
            if line.strip()
        ]
    result = [str(q).strip() for q in questions if str(q).strip()]
    return result + extras
