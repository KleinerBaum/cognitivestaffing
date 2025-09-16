"""High-level extraction and suggestion helpers built on the OpenAI API."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import streamlit as st

from config import OPENAI_MODEL
from . import api
from .api import _chat_content
from .tools import build_extraction_tool


def extract_company_info(text: str, model: str | None = None) -> dict:
    """Extract company details from website text using OpenAI.

    Args:
        text: Combined textual content of company web pages.
        model: Optional model override for the OpenAI call.

    Returns:
        Dictionary with keys ``name``, ``location``, ``mission``, ``culture`` when
        extraction succeeds. Empty dict if no information could be obtained.
    """

    text = text.strip()
    if not text:
        return {}
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)

    prompt = (
        "Analyze the following company website text and extract: the official "
        "company name, the primary location or headquarters, the company's "
        "mission or mission statement, core values or culture. Respond in JSON "
        "with keys name, location, mission, culture.\n\n"
        f"{text}"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        res = api.call_chat_api(
            messages,
            model=model,
            temperature=0.1,
            max_tokens=500,
            json_schema={
                "name": "company_info",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "location": {"type": "string"},
                        "mission": {"type": "string"},
                        "culture": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        )
        data = json.loads(_chat_content(res))
    except Exception:
        data = {}

    result: dict[str, str] = {}
    if isinstance(data, dict):
        for key in ("name", "location", "mission", "culture"):
            val = data.get(key, "")
            if isinstance(val, str):
                val = val.strip()
            if val:
                result[key] = val
    if result:
        return result

    # Fallback: simple keyword extraction if the model call fails.
    try:
        mission = ""
        culture = ""
        for line in text.splitlines():
            low = line.lower()
            if not mission and ("mission" in low or "auftrag" in low):
                mission = line.strip()
            if not culture and ("culture" in low or "kultur" in low or "werte" in low):
                culture = line.strip()
        if mission:
            result["mission"] = mission
        if culture:
            result["culture"] = culture
    except Exception:
        pass
    return result


FUNCTION_NAME = "cognitive_needs_extract"


def _extract_tool_arguments(result: api.ChatCallResult) -> str | None:
    """Return the raw ``arguments`` string from the first tool call."""

    for call in result.tool_calls or []:
        func = call.get("function") if isinstance(call, dict) else None
        if func is None and isinstance(call, dict):
            # ``call_chat_api`` normalises responses, but keep a fallback.
            func = {
                "arguments": call.get("arguments"),
            }
        if not func:
            continue
        args = func.get("arguments")
        if isinstance(args, str) and args.strip():
            return args
    return None


def _load_json_payload(payload: Any) -> dict[str, Any]:
    """Parse ``payload`` into a dictionary, repairing simple syntax issues."""

    if isinstance(payload, Mapping):
        return dict(payload)
    if not isinstance(payload, str):
        raise ValueError("Structured extraction payload must be a JSON string.")

    text = payload.strip()
    if not text:
        raise ValueError("Structured extraction payload is empty.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        fragment = text[start : end + 1]
        data = json.loads(fragment)

    if not isinstance(data, dict):
        raise ValueError("Model returned JSON that is not an object.")
    return data


def extract_with_function(
    job_text: str, schema: dict, *, model: str | None = None
) -> Mapping[str, Any]:
    """Extract profile data from ``job_text`` using OpenAI function calling.

    The helper performs two attempts:

    1. Request a ``function_call`` using ``build_extraction_tool``. When the
       model obeys, its arguments are parsed directly.
    2. If no tool call is produced, retry with ``json_mode`` that forces a
       strict JSON response.

    Minor JSON syntax issues (e.g., explanatory text around the object) are
    repaired heuristically before the data is validated against the
    ``NeedAnalysisProfile`` schema.
    """

    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)

    system_prompt = (
        "You are a vacancy extraction engine. Analyse the job advertisement "
        "and return the structured vacancy profile by calling the provided "
        f"function {FUNCTION_NAME}. Do not return free-form text."
    )
    messages: Sequence[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": job_text},
    ]

    response = api.call_chat_api(
        messages,
        model=model,
        temperature=0.0,
        tools=build_extraction_tool(FUNCTION_NAME, schema, allow_extra=False),
        tool_choice={"type": "function", "name": FUNCTION_NAME},
    )

    arguments = _extract_tool_arguments(response)
    if not arguments:
        # Some models ignore the tool request and emit plain text. Retry forcing
        # JSON mode to keep the pipeline deterministic.
        retry_messages: Sequence[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Return only valid JSON that conforms exactly to the "
                    "provided schema."
                ),
            },
            {"role": "user", "content": job_text},
        ]
        second = api.call_chat_api(
            retry_messages,
            model=model,
            temperature=0.0,
            json_schema={"name": FUNCTION_NAME, "schema": schema},
            max_tokens=1200,
        )
        arguments = _chat_content(second)

    if not arguments or not str(arguments).strip():
        raise RuntimeError("Extraction failed: no structured data received from LLM.")

    try:
        raw = _load_json_payload(arguments)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Model returned invalid JSON") from exc

    from models.need_analysis import NeedAnalysisProfile
    from core.schema import coerce_and_fill

    profile: NeedAnalysisProfile = coerce_and_fill(raw)
    return profile.model_dump()


def suggest_additional_skills(
    job_title: str,
    responsibilities: str = "",
    existing_skills: list[str] | None = None,
    num_suggestions: int = 10,
    lang: str = "en",
    model: str | None = None,
) -> dict:
    """Suggest a mix of technical and soft skills for the given role.

    Args:
        job_title: Target role title.
        responsibilities: Known responsibilities for context.
        existing_skills: Skills already listed by the user.
        num_suggestions: Total number of skills to request.
        lang: Language of the response ("en" or "de").
        model: Optional OpenAI model override.

    Returns:
        Dict with keys ``technical`` and ``soft`` containing suggested skills.
    """
    if existing_skills is None:
        existing_skills = []
    job_title = job_title.strip()
    if not job_title:
        return {"technical": [], "soft": []}
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    half = num_suggestions // 2
    if lang.startswith("de"):
        prompt = (
            f"Gib {half} technische und {half} soziale Fähigkeiten für die Position '{job_title}'. "
            "Antworte als JSON mit den Schlüsseln 'technical' und 'soft'. Vermeide Dubletten oder bereits aufgeführte Fähigkeiten."
        )
        if responsibilities:
            prompt += f" Wichtige Aufgaben: {responsibilities}."
        if existing_skills:
            prompt += f" Bereits aufgelistet: {', '.join(existing_skills)}."
    else:
        prompt = (
            f"Suggest {half} technical and {half} soft skills for a {job_title} role. "
            "Respond in JSON using keys 'technical' and 'soft'. Avoid duplicates or skills already listed."
        )
        if responsibilities:
            prompt += f" Key responsibilities: {responsibilities}."
        if existing_skills:
            prompt += f" Already listed: {', '.join(existing_skills)}."

    messages = [{"role": "user", "content": prompt}]
    max_tokens = 220 if not model or "nano" in model else 300
    res = api.call_chat_api(
        messages,
        model=model,
        temperature=0.4,
        max_tokens=max_tokens,
        json_schema={
            "name": "skill_mix",
            "schema": {
                "type": "object",
                "properties": {
                    "technical": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "soft": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["technical", "soft"],
                "additionalProperties": False,
            },
        },
    )
    answer = _chat_content(res)
    tech_skills: list[str] = []
    soft_skills: list[str] = []
    try:
        data = json.loads(answer)
        if isinstance(data, dict):
            tech_skills = [
                str(s).strip() for s in data.get("technical", []) if str(s).strip()
            ]
            soft_skills = [
                str(s).strip() for s in data.get("soft", []) if str(s).strip()
            ]
    except Exception:
        bucket = "tech"
        for line in answer.splitlines():
            skill = line.strip("-•* \t")
            if not skill:
                continue
            if skill.lower().startswith("soft"):
                bucket = "soft"
                continue
            if skill.lower().startswith("technical") or skill.lower().startswith(
                "technische"
            ):
                bucket = "tech"
                continue
            if bucket == "tech":
                tech_skills.append(skill)
            else:
                soft_skills.append(skill)
    # Normalize skill labels via ESCO and drop duplicates against existing skills
    try:
        from core.esco_utils import normalize_skills

        existing_norm = {
            s.lower() for s in normalize_skills(existing_skills, lang=lang)
        }
        tech_skills = [
            s
            for s in normalize_skills(tech_skills, lang=lang)
            if s.lower() not in existing_norm
        ]
        soft_skills = [
            s
            for s in normalize_skills(soft_skills, lang=lang)
            if s.lower() not in existing_norm
        ]
    except Exception:
        existing_lower = {s.lower() for s in existing_skills}
        tech_skills = [s for s in tech_skills if s.lower() not in existing_lower]
        soft_skills = [s for s in soft_skills if s.lower() not in existing_lower]
    return {"technical": tech_skills, "soft": soft_skills}


def suggest_skills_for_role(
    job_title: str,
    *,
    lang: str = "en",
    model: str | None = None,
) -> dict[str, list[str]]:
    """Suggest tools, hard skills and soft skills for a job title.

    Args:
        job_title: Target role title.
        lang: Output language ("en" or "de").
        model: Optional OpenAI model override.

    Returns:
        Dict with keys ``tools_and_technologies``, ``hard_skills`` and
        ``soft_skills`` each containing up to 10 suggestions.
    """

    job_title = job_title.strip()
    if not job_title:
        return {
            "tools_and_technologies": [],
            "hard_skills": [],
            "soft_skills": [],
        }
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)

    if lang.startswith("de"):
        prompt = (
            "Gib exakt 10 IT-Technologien, 10 Hard Skills und 10 Soft Skills für "
            f"den Jobtitel '{job_title}'. Antworte als JSON mit den Schlüsseln "
            "'tools_and_technologies', 'hard_skills' und 'soft_skills'."
        )
    else:
        prompt = (
            "List exactly 10 IT technologies, 10 hard skills and 10 soft skills "
            f"relevant for the job title '{job_title}'. Respond with JSON using "
            "the keys 'tools_and_technologies', 'hard_skills' and 'soft_skills'."
        )

    messages = [{"role": "user", "content": prompt}]
    res = api.call_chat_api(
        messages,
        model=model,
        json_schema={
            "name": "skill_suggestions",
            "schema": {
                "type": "object",
                "properties": {
                    "tools_and_technologies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "hard_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "soft_skills": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "tools_and_technologies",
                    "hard_skills",
                    "soft_skills",
                ],
                "additionalProperties": False,
            },
        },
        max_tokens=400,
    )
    raw = _chat_content(res)
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    def _clean(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        cleaned = [
            str(it).strip() for it in items if isinstance(it, str) and it.strip()
        ]
        return cleaned[:10]

    tools = _clean(data.get("tools_and_technologies"))
    hard = _clean(data.get("hard_skills"))
    soft = _clean(data.get("soft_skills"))

    try:  # Normalize via ESCO
        from core.esco_utils import normalize_skills

        tools = normalize_skills(tools, lang=lang)
        hard = normalize_skills(hard, lang=lang)
        soft = normalize_skills(soft, lang=lang)
    except Exception:
        pass

    def _unique(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in seq:
            low = item.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(item)
            if len(out) == 10:
                break
        return out

    return {
        "tools_and_technologies": _unique(tools),
        "hard_skills": _unique(hard),
        "soft_skills": _unique(soft),
    }


def suggest_benefits(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
    model: str | None = None,
) -> list[str]:
    """Suggest common benefits/perks for the given role.

    Args:
        job_title: Target role title.
        industry: Optional industry context.
        existing_benefits: Benefits already provided by the user.
        lang: Output language ("en" or "de").
        model: Optional OpenAI model override.

    Returns:
        A list of new benefit suggestions.
    """
    job_title = job_title.strip()
    if not job_title:
        return []
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    if lang.startswith("de"):
        prompt = f"Nenne bis zu 5 Vorteile oder Zusatzleistungen, die für eine Stelle als {job_title} üblich sind"
        if industry:
            prompt += f" in der Branche {industry}"
        prompt += ". Antworte als JSON-Liste und vermeide Vorteile, die bereits in der Liste unten stehen.\n"
        if existing_benefits:
            prompt += f"Bereits aufgelistet: {existing_benefits}"
    else:
        prompt = (
            f"List up to 5 benefits or perks commonly offered for a {job_title} role"
        )
        if industry:
            prompt += f" in the {industry} industry"
        prompt += ". Respond as a JSON array and avoid mentioning any benefit already listed below.\n"
        if existing_benefits:
            prompt += f"Already listed: {existing_benefits}"
    messages = [{"role": "user", "content": prompt}]
    max_tokens = 150 if not model or "nano" in model else 200
    res = api.call_chat_api(
        messages,
        model=model,
        temperature=0.5,
        max_tokens=max_tokens,
        json_schema={
            "name": "benefit_suggestions",
            "schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    )
    answer = _chat_content(res)
    benefits: list[str] = []
    try:
        data = json.loads(answer)
    except Exception:
        data = None

    def _clean_list(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        cleaned = [str(b).strip() for b in items if str(b).strip()]
        return cleaned[:5]

    def _extract_benefits(payload: Any) -> list[str]:
        if isinstance(payload, list):
            return _clean_list(payload)
        if isinstance(payload, dict):
            for key in ("items", "benefits", "values"):
                if key in payload:
                    extracted = _extract_benefits(payload.get(key))
                    if extracted:
                        return extracted
        return []

    if data is not None:
        benefits = _extract_benefits(data)

    if not benefits:
        for line in answer.splitlines():
            perk = line.strip("-•* \t")
            if perk:
                benefits.append(perk)
    existing_set = {b.strip().lower() for b in existing_benefits.splitlines()}
    filtered = [b for b in benefits if b.strip().lower() not in existing_set]
    seen: set[str] = set()
    unique: list[str] = []
    for b in filtered:
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(b)
    return unique


def suggest_role_tasks(
    job_title: str, num_tasks: int = 5, model: str | None = None
) -> list[str]:
    """Suggest a list of key responsibilities/tasks for a given job title.

    Args:
        job_title: Target role title.
        num_tasks: Number of tasks to request.
        model: Optional OpenAI model override.

    Returns:
        A list of suggested tasks.
    """
    job_title = job_title.strip()
    if not job_title:
        return []
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    prompt = f"List {num_tasks} concise core responsibilities for a {job_title} role as a JSON array."
    messages = [{"role": "user", "content": prompt}]
    max_tokens = 180 if not model or "nano" in model else 250
    res = api.call_chat_api(
        messages,
        model=model,
        temperature=0.5,
        max_tokens=max_tokens,
        json_schema={
            "name": "task_suggestions",
            "schema": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": num_tasks,
            },
        },
    )
    answer = _chat_content(res)
    tasks: list[str] = []
    try:
        data = json.loads(answer)
        if isinstance(data, list):
            tasks = [str(t).strip() for t in data if str(t).strip()][:num_tasks]
    except Exception:
        for line in answer.splitlines():
            task = line.strip("-•* \t")
            if task:
                tasks.append(task)
    return tasks[:num_tasks]


def generate_interview_guide(
    job_title: str,
    responsibilities: str = "",
    hard_skills: Sequence[str] | str = "",
    soft_skills: Sequence[str] | str = "",
    audience: str = "general",
    num_questions: int = 5,
    lang: str = "en",
    company_culture: str = "",
    tone: str | None = None,
    model: str | None = None,
) -> str:
    """Generate an interview guide (questions + scoring rubrics) for the role.

    Args:
        job_title: Target role title.
        responsibilities: Description of role responsibilities.
        hard_skills: Technical skills required for the role.
        soft_skills: Soft skills or competencies for the role.
        audience: Intended interviewer audience.
        num_questions: Base number of questions to generate.
        lang: Output language.
        company_culture: Optional description of company culture.
        tone: Desired tone of the guide.
        model: Optional OpenAI model override.

    Returns:
        The generated interview guide text.
    """

    def _normalize(skills: Sequence[str] | str) -> list[str]:
        if isinstance(skills, str):
            parts = [p.strip() for p in skills.replace("\n", ",").split(",")]
        else:
            parts = [str(s).strip() for s in skills]
        return [p for p in parts if p]

    hard_list = _normalize(hard_skills)
    soft_list = _normalize(soft_skills)
    total_questions = (
        num_questions + len(hard_list) + len(soft_list) + (1 if company_culture else 0)
    )
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    job_title = job_title.strip() or "this position"
    if lang.startswith("de"):
        tone = tone or "professionell und hilfreich"
        prompt = (
            f"Erstelle einen Leitfaden für ein Vorstellungsgespräch für die Position {job_title} "
            f"(für Interviewer: {audience}).\n"
            f"Formuliere {total_questions} Schlüsselfragen für das Interview und gib für jede Frage kurz die idealen Antwortkriterien an.\n"
            f"Wichtige Aufgaben der Rolle: {responsibilities or 'N/A'}.\n"
            f"Tonfall: {tone}."
        )
        if hard_list:
            prompt += (
                f"\nWichtige technische Fähigkeiten für die Rolle: {', '.join(hard_list)}."
                "\nFüge für jede dieser Fähigkeiten eine Frage hinzu, um die Expertise des Kandidaten zu bewerten."
            )
        if soft_list:
            prompt += (
                f"\nWichtige Soft Skills: {', '.join(soft_list)}."
                "\nFüge Fragen hinzu, die diese Soft Skills evaluieren."
            )
        if company_culture:
            prompt += (
                f"\nUnternehmenskultur: {company_culture}."
                "\nFüge mindestens eine Frage hinzu, die die Passung zur Unternehmenskultur bewertet."
            )
    else:
        tone = tone or "professional and helpful"
        prompt = (
            f"Generate an interview guide for a {job_title} for {audience} interviewers.\n"
            f"Include {total_questions} key interview questions and, for each question, provide a brief scoring rubric or ideal answer criteria.\n"
            f"Key responsibilities for the role: {responsibilities or 'N/A'}.\n"
            f"Tone: {tone}."
        )
        if hard_list:
            prompt += (
                f"\nKey required hard skills: {', '.join(hard_list)}."
                "\nInclude one question to assess each of these skills."
            )
        if soft_list:
            prompt += (
                f"\nImportant soft skills: {', '.join(soft_list)}."
                "\nInclude questions to evaluate these competencies."
            )
        if company_culture:
            prompt += (
                f"\nCompany culture: {company_culture}."
                "\nInclude at least one question assessing cultural fit."
            )
    messages = [{"role": "user", "content": prompt}]
    return _chat_content(
        api.call_chat_api(messages, model=model, temperature=0.7, max_tokens=1000)
    )


def generate_job_ad(
    session_data: dict, tone: str | None = None, model: str | None = None
) -> str:
    """Generate a compelling job advertisement using the collected session data."""

    def _format(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v)
        return str(value)

    # Normalize aliases and ensure we have the latest values
    data = dict(session_data)  # copy to avoid mutating original
    # Clean up benefit entries and deduplicate
    raw_benefits = data.get("compensation.benefits")
    if raw_benefits:
        if isinstance(raw_benefits, str):
            parts = [p.strip() for p in raw_benefits.splitlines() if p.strip()]
        elif isinstance(raw_benefits, list):
            parts = [str(p).strip() for p in raw_benefits if str(p).strip()]
        else:
            parts = []
        deduped: list[str] = []
        seen: set[str] = set()
        for perk in parts:
            lowered = perk.lower()
            if lowered not in seen:
                seen.add(lowered)
                deduped.append(perk)
        data["compensation.benefits"] = deduped
    lang = data.get("lang", "en")
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    if tone is None:
        tone = (
            "klar, ansprechend und inklusiv"
            if lang.startswith("de")
            else "engaging, clear, and inclusive"
        )
    # Define field labels and which session keys to use
    fields_for_ad = [
        # (session_key, English Label, German Label)
        ("position.job_title", "Job Title", "Jobtitel"),
        ("company.name", "Company", "Unternehmen"),
        ("company.size", "Company Size", "Unternehmensgröße"),
        ("location.primary_city", "Location", "Standort"),
        ("company.industry", "Industry", "Branche"),
        ("employment.job_type", "Job Type", "Anstellungsart"),
        ("employment.employment_term", "Employment Term", "Vertragsart"),
        ("employment.work_policy", "Work Policy", "Arbeitsmodell"),
        ("employment.work_schedule", "Work Schedule", "Arbeitszeit"),
        (
            "employment.work_hours_per_week",
            "Hours per Week",
            "Wochenstunden",
        ),
        ("employment.travel_required", "Travel Requirements", "Reisebereitschaft"),
        (
            "employment.relocation_support",
            "Relocation Assistance",
            "Umzugsunterstützung",
        ),
        (
            "employment.visa_sponsorship",
            "Visa Sponsorship",
            "Visum-Patenschaft",
        ),
        ("position.role_summary", "Role Summary", "Rollenbeschreibung"),
        ("responsibilities.items", "Key Responsibilities", "Wichtigste Aufgaben"),
        (
            "requirements.hard_skills_required",
            "Hard Skills (Must-have)",
            "Technische Fähigkeiten (Muss)",
        ),
        (
            "requirements.hard_skills_optional",
            "Hard Skills (Nice-to-have)",
            "Technische Fähigkeiten (Optional)",
        ),
        (
            "requirements.soft_skills_required",
            "Soft Skills (Must-have)",
            "Soziale Fähigkeiten (Muss)",
        ),
        (
            "requirements.soft_skills_optional",
            "Soft Skills (Nice-to-have)",
            "Soziale Fähigkeiten (Optional)",
        ),
        ("compensation.benefits", "Benefits", "Leistungen"),
        (
            "learning_opportunities",
            "Learning & Development",
            "Weiterbildung & Entwicklung",
        ),
        (
            "compensation.learning_budget",
            "Learning Budget",
            "Weiterbildungsbudget",
        ),
        ("position.reporting_line", "Reporting Line", "Berichtsweg"),
        ("position.team_structure", "Team Structure", "Teamstruktur"),
        ("position.team_size", "Team Size", "Teamgröße"),
        ("position.key_projects", "Key Projects", "Schlüsselprojekte"),
        ("meta.application_deadline", "Application Deadline", "Bewerbungsschluss"),
        ("position.seniority_level", "Seniority Level", "Erfahrungsebene"),
        (
            "requirements.languages_required",
            "Languages Required",
            "Erforderliche Sprachen",
        ),
        (
            "requirements.tools_and_technologies",
            "Tools and Technologies",
            "Tools und Technologien",
        ),
    ]
    details: list[str] = []
    yes_no = ("Ja", "Nein") if lang.startswith("de") else ("Yes", "No")
    boolean_fields = {
        "employment.travel_required",
        "employment.visa_sponsorship",
    }

    for key, label_en, label_de in fields_for_ad:
        val = data.get(key, "")
        if not val:
            continue
        formatted = _format(val).strip()
        if not formatted:
            continue
        label = label_de if lang.startswith("de") else label_en

        if key == "employment.travel_required":
            detail = str(data.get("employment.travel_details", "")).strip()
            if detail:
                formatted = detail
            else:
                formatted = (
                    yes_no[0] if str(val).lower() in ["true", "yes", "1"] else yes_no[1]
                )
        elif key == "employment.work_policy":
            detail = str(data.get("employment.work_policy_details", "")).strip()
            if not detail:
                perc = data.get("employment.remote_percentage")
                if perc:
                    detail = (
                        f"{perc}% remote"
                        if not lang.startswith("de")
                        else f"{perc}% Home-Office"
                    )
            if detail:
                formatted = f"{formatted} ({detail})"
        elif key == "employment.relocation_support":
            detail = str(data.get("employment.relocation_details", "")).strip()
            if detail:
                formatted = detail
            else:
                formatted = (
                    yes_no[0] if str(val).lower() in ["true", "yes", "1"] else yes_no[1]
                )
        elif key in boolean_fields:
            formatted = (
                yes_no[0] if str(val).lower() in ["true", "yes", "1"] else yes_no[1]
            )

        details.append(f"{label}: {formatted}")
    # Handle salary range as a special case
    if data.get("compensation.salary_provided"):
        try:
            min_sal = int(data.get("compensation.salary_min", 0))
            max_sal = int(data.get("compensation.salary_max", 0))
        except Exception:
            min_sal = max_sal = 0
        if min_sal or max_sal:
            currency = data.get("compensation.salary_currency", "EUR")
            period = data.get("compensation.salary_period", "year")
            salary_label = "Gehaltsspanne" if lang.startswith("de") else "Salary Range"
            if min_sal and max_sal:
                salary_str = f"{min_sal:,}–{max_sal:,} {currency} per {period}"
            else:
                # If only one value provided, use it as fixed or minimum salary
                salary_str = f"{max_sal or min_sal:,} {currency} per {period}"
            details.append(f"{salary_label}: {salary_str}")
    # Add mission or culture if provided (optional context)
    mission = data.get("company.mission", "").strip()
    culture = data.get("company.culture", "").strip()
    if lang.startswith("de"):
        prompt = (
            "Erstelle eine ansprechende, professionelle Stellenanzeige in Markdown-Format.\n"
            + "\n".join(details)
            + f"\nTonfall: {tone}."
        )
        if mission or culture:
            lines_de: list[str] = []
            if mission:
                lines_de.append(f"Unternehmensmission: {mission}")
            if culture:
                lines_de.append(f"Unternehmenskultur: {culture}")
            prompt += "\n" + "\n".join(lines_de)
            prompt += "\nFüge einen Satz über Mission oder Werte des Unternehmens hinzu, um das Employer Branding zu stärken."
    else:
        prompt = (
            "Create an engaging, professional job advertisement in Markdown format.\n"
            + "\n".join(details)
            + f"\nTone: {tone}."
        )
        if mission or culture:
            lines_en: list[str] = []
            if mission:
                lines_en.append(f"Company Mission: {mission}")
            if culture:
                lines_en.append(f"Company Culture: {culture}")
            prompt += "\n" + "\n".join(lines_en)
            prompt += "\nInclude a brief statement about the company's mission or values to strengthen employer branding."
    messages = [{"role": "user", "content": prompt}]
    return _chat_content(
        api.call_chat_api(messages, model=model, temperature=0.7, max_tokens=600)
    )


def refine_document(original: str, feedback: str, model: str | None = None) -> str:
    """Adjust a generated document using user feedback.

    Args:
        original: The original generated document.
        feedback: Instructions from the user describing desired changes.
        model: Optional OpenAI model override.

    Returns:
        The revised document text.
    """
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    prompt = (
        "Revise the following document based on the user instructions.\n"
        f"Document:\n{original}\n\n"
        f"Instructions: {feedback}"
    )
    messages = [{"role": "user", "content": prompt}]
    return _chat_content(
        api.call_chat_api(messages, model=model, temperature=0.7, max_tokens=800)
    )


def what_happened(
    session_data: dict,
    output: str,
    doc_type: str = "document",
    model: str | None = None,
) -> str:
    """Explain how a document was generated and which keys were used.

    Args:
        session_data: Session state containing source fields.
        output: The generated document text.
        doc_type: Human-readable name of the document.
        model: Optional OpenAI model override.

    Returns:
        Explanation text summarizing the generation process.
    """
    if model is None:
        model = st.session_state.get("model", OPENAI_MODEL)
    keys_used = [k for k, v in session_data.items() if v]
    prompt = (
        f"Explain how the following {doc_type} was generated using the keys: {', '.join(keys_used)}.\n"
        f"{doc_type.title()}:\n{output}"
    )
    messages = [{"role": "user", "content": prompt}]
    return _chat_content(
        api.call_chat_api(messages, model=model, temperature=0.3, max_tokens=300)
    )


__all__ = [
    "extract_company_info",
    "extract_with_function",
    "suggest_additional_skills",
    "suggest_skills_for_role",
    "suggest_benefits",
    "suggest_role_tasks",
    "generate_interview_guide",
    "generate_job_ad",
    "refine_document",
    "what_happened",
]
