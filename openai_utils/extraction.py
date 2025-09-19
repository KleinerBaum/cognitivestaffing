"""High-level extraction and suggestion helpers built on the OpenAI API."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config import ModelTask, get_model_for
from core.job_ad import JOB_AD_FIELDS, iter_field_keys
from llm.rag_pipeline import (
    FieldExtractionContext,
    RetrievedChunk,
    build_global_context as default_global_context,
)
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
        model = get_model_for(ModelTask.COMPANY_INFO)

    expected_fields = ("name", "location", "mission", "culture")
    properties = {field: {"type": "string"} for field in expected_fields}

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
                    "properties": properties,
                    "required": list(properties.keys()),
                    "additionalProperties": False,
                },
            },
        )
        data = json.loads(_chat_content(res))
    except Exception:
        data = {}

    result: dict[str, str] = {}
    if isinstance(data, dict):
        for key in expected_fields:
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


@dataclass(slots=True)
class ExtractionResult:
    """Structured result returned by :func:`extract_with_function`."""

    data: Mapping[str, Any]
    field_contexts: Mapping[str, FieldExtractionContext]
    global_context: Sequence[RetrievedChunk]


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
    job_text: str,
    schema: dict,
    *,
    model: str | None = None,
    field_contexts: Mapping[str, FieldExtractionContext] | None = None,
    global_context: Sequence[RetrievedChunk] | None = None,
) -> ExtractionResult:
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
        model = get_model_for(ModelTask.EXTRACTION)

    if field_contexts:
        if global_context is None:
            global_context = default_global_context(job_text)
        payload = {
            "global_context": [chunk.to_payload() for chunk in global_context],
            "fields": [
                {
                    "field": ctx.field,
                    "instruction": ctx.instruction,
                    "context": [chunk.to_payload() for chunk in ctx.chunks],
                }
                for ctx in field_contexts.values()
            ],
        }
        system_prompt = (
            "You are a vacancy extraction engine. Use the provided global context "
            "and the per-field snippets to populate the vacancy schema by calling "
            f"the function {FUNCTION_NAME}. If no relevant snippet is provided "
            "for a field, return an empty string or empty list. Do not invent data."
        )
        messages: Sequence[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
    else:
        system_prompt = (
            "You are a vacancy extraction engine. Analyse the job advertisement "
            "and return the structured vacancy profile by calling the provided "
            f"function {FUNCTION_NAME}. Do not return free-form text."
        )
        messages = [
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
    return ExtractionResult(
        data=profile.model_dump(),
        field_contexts=field_contexts or {},
        global_context=global_context or [],
    )


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
        model = get_model_for(ModelTask.SKILL_SUGGESTION)
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
    # Normalize skill labels locally and drop duplicates against existing skills
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
        model = get_model_for(ModelTask.SKILL_SUGGESTION)

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

    try:  # Normalize skill labels locally
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
        model = get_model_for(ModelTask.BENEFIT_SUGGESTION)
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
        model = get_model_for(ModelTask.TASK_SUGGESTION)
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


def suggest_onboarding_plans(
    job_title: str,
    *,
    company_name: str = "",
    industry: str = "",
    culture: str = "",
    lang: str = "en",
    model: str | None = None,
) -> list[str]:
    """Generate onboarding program suggestions tailored to the role context."""

    job_title = job_title.strip()
    if not job_title:
        return []
    company_name = company_name.strip()
    industry = industry.strip()
    culture = culture.strip()
    if model is None:
        model = get_model_for(ModelTask.ONBOARDING_SUGGESTION)

    is_de = lang.lower().startswith("de")
    if is_de:
        prompt = (
            "Du bist ein HR-Experte. Entwickle fünf kurze, konkrekte Vorschläge "
            "für den Onboarding-Prozess einer neuen Fachkraft."
        )
        prompt += f"\nRolle: {job_title}."
        if company_name:
            prompt += f"\nUnternehmen: {company_name}."
        if industry:
            prompt += f"\nBranche: {industry}."
        if culture:
            prompt += f"\nUnternehmenskultur oder Werte: {culture}."
        prompt += (
            "\nJeder Vorschlag sollte eine eigenständige Maßnahme mit Fokus auf "
            "Kommunikation, Wissensaufbau oder Integration sein."
            "\nFormatiere die Ausgabe als JSON-Array mit genau fünf String-Elementen."
        )
    else:
        prompt = (
            "You are an HR expert. Devise five concise, actionable onboarding "
            "initiatives for a new hire."
        )
        prompt += f"\nRole: {job_title}."
        if company_name:
            prompt += f"\nCompany: {company_name}."
        if industry:
            prompt += f"\nIndustry: {industry}."
        if culture:
            prompt += f"\nCompany culture or values: {culture}."
        prompt += (
            "\nEach suggestion should describe a single activity focusing on "
            "communication, knowledge transfer, or integration."
            "\nReturn the result as a JSON array with exactly five string items."
        )

    messages = [{"role": "user", "content": prompt}]
    onboarding_schema = {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": 5,
                "maxItems": 5,
            }
        },
        "required": ["suggestions"],
        "additionalProperties": False,
    }
    res = api.call_chat_api(
        messages,
        model=model,
        temperature=0.4,
        max_tokens=220,
        json_schema={
            "name": "onboarding_suggestions",
            "schema": onboarding_schema,
        },
    )
    answer = _chat_content(res)
    suggestions: list[str] = []
    payload: Any
    try:
        payload = json.loads(answer)
    except Exception:
        payload = None

    suggestions_payload: Sequence[Any] = []
    if isinstance(payload, Mapping):
        suggestions_payload = payload.get("suggestions", [])
    elif isinstance(payload, list):
        suggestions_payload = payload

    if not isinstance(suggestions_payload, Sequence) or isinstance(
        suggestions_payload, (str, bytes)
    ):
        suggestions_payload = []

    try:
        suggestions = [
            str(item).strip() for item in suggestions_payload if str(item).strip()
        ]
    except Exception:
        for line in answer.splitlines():
            item = line.strip("-•* \t")
            if item:
                suggestions.append(item)

    seen: set[str] = set()
    unique: list[str] = []
    for suggestion in suggestions:
        key = suggestion.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(suggestion)
        if len(unique) == 5:
            break
    return unique


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
        model = get_model_for(ModelTask.INTERVIEW_GUIDE)
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
    session_data: Mapping[str, Any],
    selected_fields: Sequence[str],
    *,
    target_audience: str,
    manual_sections: Sequence[Mapping[str, str]] | None = None,
    style_reference: str | None = None,
    lang: str | None = None,
    model: str | None = None,
    selected_values: Mapping[str, Any] | None = None,
) -> str:
    """Generate a job advertisement tailored to the selected audience."""

    if not selected_fields:
        raise ValueError("No fields selected for job ad generation.")
    audience_text = (target_audience or "").strip()
    if not audience_text:
        raise ValueError("Target audience is required for job ad generation.")

    data = dict(session_data)

    def _resolve(path: str) -> Any:
        if path in data:
            return data[path]
        parts = path.split(".")
        cursor: Any = data
        for part in parts:
            if isinstance(cursor, Mapping) and part in cursor:
                cursor = cursor[part]
            else:
                return None
        return cursor

    def _normalize_benefits(raw: Any) -> list[str]:
        if isinstance(raw, list):
            items = [str(item).strip() for item in raw if str(item).strip()]
        elif isinstance(raw, str):
            items = [p.strip() for p in raw.splitlines() if p.strip()]
        else:
            return []
        seen: set[str] = set()
        result: list[str] = []
        for perk in items:
            low = perk.lower()
            if low not in seen:
                seen.add(low)
                result.append(perk)
        return result

    lang_code = (lang or data.get("lang") or "de").lower()
    is_de = lang_code.startswith("de")
    yes_no = ("Ja", "Nein") if is_de else ("Yes", "No")

    known_keys = {field.key for field in JOB_AD_FIELDS}

    def _normalize_key(field_id: str) -> str | None:
        if field_id in known_keys:
            return field_id
        base, _, _ = field_id.partition("::")
        return base if base in known_keys else None

    ordered_keys: list[str] = []
    seen_keys: set[str] = set()
    for entry in selected_fields:
        normalised = _normalize_key(entry)
        if normalised and normalised not in seen_keys:
            seen_keys.add(normalised)
            ordered_keys.append(normalised)
    if not ordered_keys:
        ordered_keys = list(iter_field_keys(selected_fields))

    selected = set(ordered_keys)
    overrides: dict[str, list[Any]] = {key: [] for key in selected}

    def _extend_override(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            overrides[key].extend(value)
            return
        if isinstance(value, set):
            overrides[key].extend(sorted(value))
            return
        overrides[key].append(value)

    def _extract_selected_values() -> Mapping[str, Any]:
        if isinstance(selected_values, Mapping):
            return selected_values
        if isinstance(session_data, Mapping):
            nested = session_data.get("data.job_ad.selected_values")
            if isinstance(nested, Mapping):
                return nested
            data_section = session_data.get("data")
            if isinstance(data_section, Mapping):
                job_ad_section = data_section.get("job_ad")
                if isinstance(job_ad_section, Mapping):
                    nested = job_ad_section.get("selected_values")
                    if isinstance(nested, Mapping):
                        return nested
        return {}

    def _lookup_selected_value(field_id: str, source: Mapping[str, Any]) -> Any | None:
        if field_id in source:
            return source[field_id]
        base_key, sep, suffix = field_id.partition("::")
        base_value = source.get(base_key)
        if sep and base_value is not None:
            if isinstance(base_value, Mapping):
                if suffix in base_value:
                    return base_value[suffix]
                try:
                    index = int(suffix)
                except ValueError:
                    index = None
                if index is not None:
                    if index in base_value:
                        return base_value[index]
                    str_index = str(index)
                    if str_index in base_value:
                        return base_value[str_index]
                values = (
                    base_value.get("values")
                    if isinstance(base_value, Mapping)
                    else None
                )
                if isinstance(values, Sequence):
                    try:
                        idx = int(suffix)
                    except ValueError:
                        idx = None
                    if idx is not None and -len(values) <= idx < len(values):
                        return values[idx]
                value_entry = base_value.get("value")
                if value_entry is not None:
                    return value_entry
            if isinstance(base_value, Sequence) and not isinstance(
                base_value, (str, bytes)
            ):
                try:
                    idx = int(suffix)
                except ValueError:
                    idx = None
                if idx is not None and -len(base_value) <= idx < len(base_value):
                    return base_value[idx]
            if isinstance(base_value, str):
                parts = [
                    part.strip() for part in base_value.splitlines() if part.strip()
                ]
                if parts:
                    try:
                        idx = int(suffix)
                    except ValueError:
                        idx = None
                    if idx is not None and -len(parts) <= idx < len(parts):
                        return parts[idx]
        if isinstance(base_value, Mapping):
            if "value" in base_value:
                return base_value["value"]
            if "values" in base_value and isinstance(base_value["values"], Sequence):
                return list(base_value["values"])
        if base_value is not None:
            return base_value
        return None

    values_source = _extract_selected_values()
    if values_source:
        for entry_id in selected_fields:
            field_key = _normalize_key(entry_id)
            if not field_key or field_key not in overrides:
                continue
            override_value = _lookup_selected_value(entry_id, values_source)
            if override_value is None:
                continue
            _extend_override(field_key, override_value)
    details: list[str] = []

    def _format_value(key: str, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        if key == "compensation.benefits":
            perks = _normalize_benefits(value)
            if not perks:
                return None
            return ", ".join(perks)
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return ", ".join(cleaned) if cleaned else None
        if isinstance(value, bool):
            return yes_no[0] if value else yes_no[1]
        return str(value)

    def _format_detail(field_key: str, override_value: Any | None = None) -> None:
        if override_value is not None:
            formatted_override = _format_value(field_key, override_value)
            if not formatted_override:
                return
            label = next(
                (
                    field.label_de if is_de else field.label_en
                    for field in JOB_AD_FIELDS
                    if field.key == field_key
                ),
                field_key,
            )
            details.append(f"{label}: {formatted_override}")
            return

        if field_key == "compensation.salary":
            salary_enabled = bool(_resolve("compensation.salary_provided"))
            if not salary_enabled:
                return
            min_val = _resolve("compensation.salary_min")
            max_val = _resolve("compensation.salary_max")
            currency = _resolve("compensation.currency") or "EUR"
            period = _resolve("compensation.period") or ("Jahr" if is_de else "year")
            if not min_val and not max_val:
                return
            if min_val and max_val:
                salary_text = f"{int(min_val):,}–{int(max_val):,} {currency} / {period}"
            else:
                amount = int(max_val or min_val or 0)
                salary_text = f"{amount:,} {currency} / {period}"
            label = next(
                (
                    field.label_de if is_de else field.label_en
                    for field in JOB_AD_FIELDS
                    if field.key == field_key
                ),
                "Salary",
            )
            details.append(f"{label}: {salary_text}")
            return

        raw_value = _resolve(field_key)
        if field_key == "employment.travel_required":
            detail = _resolve("employment.travel_details")
            if detail:
                raw_value = detail
            elif raw_value is not None:
                raw_value = bool(raw_value)
        elif field_key == "employment.relocation_support":
            detail = _resolve("employment.relocation_details")
            if detail:
                raw_value = detail
            elif raw_value is not None:
                raw_value = bool(raw_value)
        elif field_key == "employment.work_policy":
            details_text = _resolve("employment.work_policy_details")
            if not details_text:
                percentage = _resolve("employment.remote_percentage")
                if percentage:
                    details_text = (
                        f"{percentage}% Home-Office"
                        if is_de
                        else f"{percentage}% remote"
                    )
            if details_text and isinstance(raw_value, str):
                raw_value = f"{raw_value.strip()} ({details_text})"
        elif field_key == "employment.remote_percentage" and raw_value:
            suffix = "% Home-Office" if is_de else "% remote"
            raw_value = f"{raw_value}{suffix}"

        formatted = _format_value(field_key, raw_value)
        if not formatted:
            return
        label = next(
            (
                field.label_de if is_de else field.label_en
                for field in JOB_AD_FIELDS
                if field.key == field_key
            ),
            field_key,
        )
        details.append(f"{label}: {formatted}")

    for field in JOB_AD_FIELDS:
        if field.key not in selected:
            continue
        override_values = overrides.get(field.key)
        selected_override: Any | None
        if override_values:
            selected_override = (
                override_values if len(override_values) > 1 else override_values[0]
            )
        else:
            selected_override = None
        _format_detail(field.key, selected_override)

    extra_sections = manual_sections or []
    for section in extra_sections:
        content = str(section.get("content", "")).strip()
        if not content:
            continue
        title = str(section.get("title", "")).strip()
        if title:
            details.append(f"{title}: {content}")
        else:
            details.append(content)

    if not details:
        raise ValueError("No usable data available for the job ad.")

    style_text = (style_reference or "").strip()
    intro = (
        "Erstelle eine vollständige, SEO-optimierte Stellenanzeige im Markdown-Format."
        if is_de
        else "Create a complete, SEO-optimised job advertisement in Markdown format."
    )
    compliance = (
        "Achte auf inklusive, diskriminierungsfreie Sprache und erfülle die DSGVO."
        if is_de
        else "Use inclusive, non-discriminatory language and ensure GDPR compliance."
    )
    structure = (
        "Nutze klare Überschriften, eine motivierende Einleitung und einen eindeutigen Call-to-Action am Ende."
        if is_de
        else "Use clear headings, an engaging introduction and end with a precise call to action."
    )
    audience_line = (
        f"Zielgruppe: {audience_text}."
        if is_de
        else f"Target audience: {audience_text}."
    )
    if style_text:
        style_line = (
            f"Berücksichtige Marken-/Styleguide-Hinweise: {style_text}."
            if is_de
            else f"Incorporate these brand/style guidelines: {style_text}."
        )
    else:
        style_line = ""

    prompt_parts = [intro, audience_line, compliance, structure]
    if style_line:
        prompt_parts.append(style_line)
    prompt_parts.append(
        "Relevante Informationen:" if is_de else "Relevant information:"
    )
    prompt_parts.extend(details)
    prompt_parts.append(
        "Schließe mit einem prägnanten Abschnitt zu Benefits, Datenschutz und Bewerbungsprozess."
        if is_de
        else "Conclude with a concise section covering benefits, data privacy and how to apply."
    )

    prompt = "\n".join(prompt_parts)

    if model is None:
        model = get_model_for(ModelTask.JOB_AD)

    messages = [{"role": "user", "content": prompt}]
    return _chat_content(
        api.call_chat_api(messages, model=model, temperature=0.7, max_tokens=700)
    )


def summarize_company_page(
    text: str,
    section: str,
    *,
    lang: str = "de",
    model: str | None = None,
) -> str:
    """Summarize a company web page into a concise paragraph.

    Args:
        text: Extracted page text that should be summarised.
        section: Human-readable label for the section (e.g. "About" or
            "Impressum").
        lang: Target language for the summary (``"de"`` or ``"en"`` supported).
        model: Optional OpenAI model override.

    Returns:
        A summary string describing the most relevant information.
    """

    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000]
    if model is None:
        model = get_model_for(ModelTask.EXPLANATION)

    if lang.lower().startswith("de"):
        prompt = (
            "Fasse den folgenden Text in maximal vier Sätzen zusammen."
            " Hebe nur die wichtigsten Fakten hervor. Abschnitt: "
            f"{section}.\n\n{cleaned}"
        )
    else:
        prompt = (
            "Summarise the following text in at most four sentences,"
            " focusing on the key facts only. Section: "
            f"{section}.\n\n{cleaned}"
        )

    messages = [{"role": "user", "content": prompt}]
    try:
        summary = _chat_content(
            api.call_chat_api(messages, model=model, temperature=0.2, max_tokens=220)
        ).strip()
    except Exception:
        summary = ""

    if summary:
        return summary

    return textwrap.shorten(cleaned, width=420, placeholder="…")


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
        model = get_model_for(ModelTask.DOCUMENT_REFINEMENT)
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
        model = get_model_for(ModelTask.EXPLANATION)
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
    "ExtractionResult",
    "suggest_additional_skills",
    "suggest_skills_for_role",
    "suggest_benefits",
    "suggest_role_tasks",
    "suggest_onboarding_plans",
    "generate_interview_guide",
    "generate_job_ad",
    "summarize_company_page",
    "refine_document",
    "what_happened",
]
