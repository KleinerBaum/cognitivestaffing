"""High-level extraction and suggestion helpers built on the OpenAI API."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from config import ModelTask, get_model_for
from core.job_ad import JOB_AD_FIELDS, JOB_AD_GROUP_LABELS, iter_field_keys
from llm.prompts import build_job_ad_prompt
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
    """Create an interview preparation guide directly from captured profile data."""

    lang_code = (lang or "de").lower()
    is_de = lang_code.startswith("de")

    def _tr(value_de: str, value_en: str) -> str:
        return value_de if is_de else value_en

    def _normalise_list(payload: Sequence[str] | str) -> list[str]:
        if isinstance(payload, str):
            parts = [p.strip() for p in payload.replace('\r', '').splitlines()]
        else:
            parts = [str(item).strip() for item in payload]
        return [p for p in parts if p]

    def _sentence_case(text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        return cleaned[0].upper() + cleaned[1:]

    hard_list = _normalise_list(hard_skills)
    soft_list = _normalise_list(soft_skills)
    responsibilities_list = _normalise_list(responsibilities)

    audience_display = {
        "general": _tr("Allgemeines Interviewteam", "General interview panel"),
        "technical": _tr("Technisches Interviewteam", "Technical panel"),
        "leadership": _tr("Führungsteam", "Leadership panel"),
    }.get(audience, audience)

    job_title_text = job_title.strip() or _tr("diese Position", "this role")
    tone_text = tone.strip() if isinstance(tone, str) else ""
    if not tone_text:
        tone_text = _tr("professionell und strukturiert", "professional and structured")

    def _make_question(
        question: str,
        focus: str,
        evaluation: str,
    ) -> dict[str, str]:
        return {
            "question": _sentence_case(question),
            "focus": focus.strip(),
            "evaluation": evaluation.strip(),
        }

    focus_label = _tr("Fokus", "Focus")
    evaluation_label = _tr("Bewertungshinweise", "Evaluation guidance")

    motivation_question = _make_question(
        _tr(
            f"Was motiviert Sie an der Rolle als {job_title_text}?",
            f"What excites you most about the {job_title_text} opportunity?",
        ),
        _tr("Motivation & Passung", "Motivation & fit"),
        _tr(
            "Suchen Sie nach konkreten Beweggründen, Bezug zum Team und Erwartungen an die Rolle.",
            "Listen for concrete reasons, links to the team and expectations for the role.",
        ),
    )

    questions: list[dict[str, str]] = []

    def _add_question(entry: dict[str, str]) -> None:
        if len(questions) >= max(3, min(10, num_questions)):
            return
        key = entry["question"].strip().lower()
        if key in {q["question"].strip().lower() for q in questions}:
            return
        questions.append(entry)

    _add_question(motivation_question)

    culture_note = company_culture.strip()
    if culture_note:
        culture_question = _make_question(
            _tr(
                "Welche Aspekte unserer beschriebenen Kultur sprechen Sie besonders an und wie würden Sie sie im Alltag leben?",
                "Which aspects of the culture we described resonate with you and how would you live them day to day?",
            ),
            _tr("Kulturelle Passung", "Cultural alignment"),
            _tr(
                "Hören Sie auf Beispiele aus der Vergangenheit und darauf, wie Werte in konkretes Verhalten übersetzt werden.",
                "Listen for past examples and how values translate into concrete behaviour.",
            ),
        )
        _add_question(culture_question)

    for item in responsibilities_list[:3]:
        q = _make_question(
            _tr(
                f"Beschreiben Sie ein Projekt, in dem Sie '{item}' verantwortet haben. Wie sind Sie vorgegangen und welches Ergebnis wurde erreicht?",
                f"Describe a project where you were responsible for '{item}'. How did you approach it and what was the outcome?",
            ),
            _tr("Umsetzung zentraler Aufgaben", "Executing key responsibilities"),
            _tr(
                "Achten Sie auf Struktur, Prioritätensetzung und darauf, welchen Beitrag die Kandidat:in geleistet hat.",
                "Look for structure, prioritisation and the candidate's personal contribution.",
            ),
        )
        _add_question(q)

    for skill in hard_list[:4]:
        q = _make_question(
            _tr(
                f"Wie gehen Sie bei {skill} vor? Beschreiben Sie einen konkreten Anwendungsfall.",
                f"How do you approach {skill}? Walk us through a specific use case.",
            ),
            _tr("Technische Tiefe", "Technical depth"),
            _tr(
                "Erfragen Sie Details zu Methodik, Tools und Ergebnissen, um die tatsächliche Expertise zu bewerten.",
                "Probe for methodology, tools and measurable outcomes to judge depth of expertise.",
            ),
        )
        _add_question(q)

    for skill in soft_list[:3]:
        q = _make_question(
            _tr(
                f"Erzählen Sie von einer Situation, in der '{skill}' besonders wichtig war. Wie haben Sie reagiert?",
                f"Tell us about a situation where '{skill}' was critical. How did you respond?",
            ),
            _tr("Verhaltenskompetenzen", "Behavioural competencies"),
            _tr(
                "Achten Sie auf Selbstreflexion, Lernmomente und konkrete Resultate.",
                "Listen for self-reflection, learning and concrete outcomes.",
            ),
        )
        _add_question(q)

    fallback_questions = [
        _make_question(
            _tr(
                "Wie würden Sie Ihre ersten 90 Tage gestalten, um Wirkung zu erzielen?",
                "How would you structure your first 90 days to create impact?",
            ),
            _tr("Onboarding & Planung", "Onboarding & planning"),
            _tr(
                "Achten Sie auf Prioritäten, Stakeholder-Management und klare Lernziele.",
                "Look for prioritisation, stakeholder management and clear learning goals.",
            ),
        ),
        _make_question(
            _tr(
                "Wie gehen Sie mit kritischem Feedback um? Geben Sie bitte ein Beispiel.",
                "How do you handle critical feedback? Please give an example.",
            ),
            _tr("Selbstreflexion", "Self-awareness"),
            _tr(
                "Suchen Sie nach der Bereitschaft, Feedback anzunehmen und daraus Maßnahmen abzuleiten.",
                "Look for willingness to accept feedback and translate it into action.",
            ),
        ),
        _make_question(
            _tr(
                "Wie stellen Sie sicher, dass Sie mit anderen Teams effektiv zusammenarbeiten?",
                "How do you ensure effective collaboration with other teams?",
            ),
            _tr("Zusammenarbeit", "Collaboration"),
            _tr(
                "Achten Sie auf Kommunikationsroutinen, Transparenz und Umgang mit Konflikten.",
                "Listen for communication routines, transparency and conflict handling.",
            ),
        ),
        _make_question(
            _tr(
                "Welche Kennzahlen oder Ergebnisse nutzen Sie, um Ihren Erfolg sichtbar zu machen?",
                "Which metrics or outcomes do you use to make your success visible?",
            ),
            _tr("Ergebnisorientierung", "Outcome focus"),
            _tr(
                "Hören Sie auf Zahlen, qualitative Wirkungen und wie Erkenntnisse geteilt werden.",
                "Listen for metrics, qualitative impact and how learnings are shared.",
            ),
        ),
        _make_question(
            _tr(
                "Welche Fragen haben Sie an uns, um zu entscheiden, ob wir zueinander passen?",
                "What questions do you have for us to decide whether we're a mutual fit?",
            ),
            _tr("Abschluss & Erwartungsabgleich", "Closing & expectation alignment"),
            _tr(
                "Gute Kandidat:innen nutzen die Gelegenheit, offene Punkte strukturiert zu adressieren.",
                "Strong candidates use the chance to address open topics in a structured way.",
            ),
        ),
    ]

    for question in fallback_questions:
        _add_question(question)

    if len(questions) < num_questions:
        additional_sources = responsibilities_list[3:] + hard_list[4:] + soft_list[3:]
        for item in additional_sources:
            q = _make_question(
                _tr(
                    f"Welche Erfahrungen haben Sie mit '{item}' gesammelt und was haben Sie daraus gelernt?",
                    f"What experience do you have with '{item}' and what did you learn from it?",
                ),
                _tr("Vertiefung", "Deep dive"),
                _tr(
                    "Fragen Sie nach Ergebnissen, Lessons Learned und der Übertragbarkeit auf die Rolle.",
                    "Ask about outcomes, lessons learned and applicability to the role.",
                ),
            )
            _add_question(q)
            if len(questions) >= num_questions:
                break

    if len(questions) > num_questions:
        questions = questions[:num_questions]

    summary_lines: list[str] = []
    summary_lines.append(
        _tr("Interviewleitfaden", "Interview Guide") + f" – {job_title_text}"
    )
    summary_lines.append("")
    summary_lines.append(
        f"**{_tr('Zielgruppe', 'Intended audience')}:** {audience_display}"
    )
    summary_lines.append(f"**{_tr('Tonfall', 'Tone')}:** {tone_text}")
    if culture_note:
        summary_lines.append(
            f"**{_tr('Unternehmenskultur', 'Company culture')}:** {culture_note}"
        )

    focus_section: list[str] = []
    if responsibilities_list or hard_list or soft_list:
        focus_section.append("")
        focus_section.append(f"## {_tr('Fokusbereiche', 'Focus areas')}")
        if responsibilities_list:
            focus_section.append(
                f"- **{_tr('Schlüsselaufgaben', 'Key responsibilities')}:** "
                + ", ".join(responsibilities_list[:5])
            )
        if hard_list:
            focus_section.append(
                f"- **{_tr('Kernkompetenzen', 'Core hard skills')}:** "
                + ", ".join(hard_list[:5])
            )
        if soft_list:
            focus_section.append(
                f"- **{_tr('Soft Skills', 'Soft skills')}:** "
                + ", ".join(soft_list[:5])
            )

    question_lines: list[str] = [
        "",
        f"## {_tr('Fragen & Bewertungsleitfaden', 'Questions & evaluation guide')}",
    ]
    for idx, question in enumerate(questions, start=1):
        question_lines.append("")
        question_lines.append(f"### {idx}. {question['question']}")
        question_lines.append(f"- **{focus_label}:** {question['focus']}")
        question_lines.append(
            f"- **{evaluation_label}:** {question['evaluation']}"
        )

    document = "\n".join(summary_lines + focus_section + question_lines).strip()
    return document


def generate_job_ad(
    session_data: Mapping[str, Any],
    selected_fields: Sequence[str],
    *,
    target_audience: str,
    manual_sections: Sequence[Mapping[str, str]] | None = None,
    style_reference: str | None = None,
    tone: str | None = None,
    lang: str | None = None,
    model: str | None = None,
    selected_values: Mapping[str, Any] | None = None,
) -> str:
    """Generate a structured job advertisement from collected profile data."""

    if not selected_fields:
        raise ValueError("No fields selected for job ad generation.")
    audience_text = (target_audience or "").strip()
    if not audience_text:
        raise ValueError("Target audience is required for job ad generation.")

    data = dict(session_data)
    lang_code = (lang or data.get("lang") or "de").lower()
    is_de = lang_code.startswith("de")
    yes_no = ("Ja", "Nein") if is_de else ("Yes", "No")

    base_fields = [entry.split("::")[0] for entry in selected_fields]
    ordered_keys = list(iter_field_keys(base_fields))
    if not ordered_keys:
        raise ValueError("No usable fields selected for job ad generation.")

    field_map = {field.key: field for field in JOB_AD_FIELDS}
    group_labels = {
        key: (labels[0] if is_de else labels[1])
        for key, labels in JOB_AD_GROUP_LABELS.items()
    }

    def _resolve(path: str) -> Any:
        if path in data:
            return data[path]
        cursor: Any = data
        for part in path.split('.'):
            if isinstance(cursor, Mapping) and part in cursor:
                cursor = cursor[part]
            else:
                return None
        return cursor

    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            items = [part.strip() for part in value.replace('\r', '').splitlines() if part.strip()]
        else:
            items = []
        return items

    def _normalize_benefits(raw: Any) -> list[str]:
        items = _normalize_list(raw)
        seen: set[str] = set()
        unique: list[str] = []
        for entry in items:
            lowered = entry.lower()
            if lowered not in seen:
                seen.add(lowered)
                unique.append(entry)
        return unique

    list_field_keys = {
        "responsibilities.items",
        "requirements.hard_skills_required",
        "requirements.hard_skills_optional",
        "requirements.soft_skills_required",
        "requirements.soft_skills_optional",
        "requirements.tools_and_technologies",
        "requirements.languages_required",
        "requirements.languages_optional",
        "requirements.certifications",
        "compensation.benefits",
    }

    values_map: Mapping[str, Any]
    if isinstance(selected_values, Mapping):
        values_map = selected_values
    else:
        nested = _resolve("data.job_ad.selected_values")
        values_map = nested if isinstance(nested, Mapping) else {}

    def _value_override(field_key: str) -> Any | None:
        if not values_map:
            return None
        if field_key in values_map:
            return values_map[field_key]
        prefix = f"{field_key}::"
        collected: list[tuple[int | None, Any]] = []
        for key, value in values_map.items():
            if not isinstance(key, str) or not key.startswith(prefix):
                continue
            suffix = key[len(prefix):]
            try:
                index = int(suffix)
            except ValueError:
                index = None
            collected.append((index, value))
        if not collected:
            return None
        collected.sort(key=lambda item: item[0] if item[0] is not None else 0)
        return [val for _idx, val in collected]

    def _compose_field_value(field_key: str) -> str | list[str] | None:
        override = _value_override(field_key)
        if isinstance(override, list) and field_key not in list_field_keys:
            override = override[0] if override else None

        if field_key == "compensation.salary":
            if isinstance(override, str):
                text = override.strip()
                return text or None
            salary_enabled = bool(_resolve("compensation.salary_provided"))
            if not salary_enabled:
                return None
            if isinstance(override, Mapping):
                min_val = override.get("min") or override.get("salary_min")
                max_val = override.get("max") or override.get("salary_max")
                currency = override.get("currency") or _resolve("compensation.currency") or "EUR"
                period = override.get("period") or _resolve("compensation.period") or ("Jahr" if is_de else "year")
            else:
                min_val = _resolve("compensation.salary_min")
                max_val = _resolve("compensation.salary_max")
                currency = _resolve("compensation.currency") or "EUR"
                period = _resolve("compensation.period") or ("Jahr" if is_de else "year")
            try:
                min_num = int(min_val) if min_val else 0
            except (TypeError, ValueError):
                min_num = 0
            try:
                max_num = int(max_val) if max_val else 0
            except (TypeError, ValueError):
                max_num = 0
            if not min_num and not max_num:
                return None
            if min_num and max_num:
                return f"{min_num:,}–{max_num:,} {currency} / {period}"
            amount = max_num or min_num
            return f"{amount:,} {currency} / {period}"

        if field_key == "employment.travel_required":
            if isinstance(override, str) and override.strip():
                return override.strip()
            detail = _resolve("employment.travel_details")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
            raw = override if isinstance(override, bool) else _resolve("employment.travel_required")
            if raw in (None, ""):
                return None
            return yes_no[0] if bool(raw) else yes_no[1]

        if field_key == "employment.relocation_support":
            if isinstance(override, str) and override.strip():
                return override.strip()
            detail = _resolve("employment.relocation_details")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
            raw = override if isinstance(override, bool) else _resolve("employment.relocation_support")
            if raw in (None, ""):
                return None
            return yes_no[0] if bool(raw) else yes_no[1]

        if field_key == "employment.work_policy":
            base_value = override if isinstance(override, str) else _resolve("employment.work_policy")
            if not base_value:
                return None
            policy_detail = None
            if isinstance(override, Mapping):
                policy_detail = override.get("details")
            if not policy_detail:
                policy_detail = _resolve("employment.work_policy_details")
            if not policy_detail:
                percentage = _resolve("employment.remote_percentage")
                if percentage:
                    policy_detail = f"{percentage}% Home-Office" if is_de else f"{percentage}% remote"
            if policy_detail:
                return f"{str(base_value).strip()} ({str(policy_detail).strip()})"
            return str(base_value).strip()

        if field_key == "employment.remote_percentage":
            raw = override if override is not None else _resolve("employment.remote_percentage")
            if raw in (None, ""):
                return None
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return str(raw)
            suffix = "% Home-Office" if is_de else "% remote"
            return f"{value}{suffix}"

        if field_key == "compensation.benefits":
            source = override if override is not None else _resolve("compensation.benefits")
            perks = _normalize_benefits(source)
            return perks or None

        if field_key in list_field_keys:
            source = override if override is not None else _resolve(field_key)
            items = _normalize_list(source)
            return items or None

        if override is not None:
            raw_value = override
        else:
            raw_value = _resolve(field_key)

        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, bool):
            return yes_no[0] if raw_value else yes_no[1]
        if isinstance(raw_value, (int, float)):
            return str(raw_value)
        return str(raw_value).strip()

    entries: list[tuple[str, str, str, str | list[str]]] = []
    for key in ordered_keys:
        field_def = field_map.get(key)
        if not field_def:
            continue
        value = _compose_field_value(key)
        if value in (None, "", []):
            continue
        label = field_def.label_de if is_de else field_def.label_en
        entries.append((key, field_def.group, label, value))

    manual_sections_payload: list[dict[str, str]] = []
    if manual_sections:
        for section in manual_sections:
            content = str(section.get("content", "")).strip()
            if not content:
                continue
            title = str(section.get("title", "")).strip()
            manual_sections_payload.append({"title": title, "content": content})

    if not entries and not manual_sections_payload:
        raise ValueError("No usable data available for the job ad.")

    job_title_value = _compose_field_value("position.job_title") or ""
    company_brand = _compose_field_value("company.brand_name") or ""
    company_name = _compose_field_value("company.name") or ""
    company_display = company_brand or company_name

    if job_title_value and company_display:
        heading = (
            f"# {job_title_value} bei {company_display}"
            if is_de
            else f"# {job_title_value} at {company_display}"
        )
    elif job_title_value:
        heading = f"# {job_title_value}"
    elif company_display:
        heading = f"# {company_display}"
    else:
        heading = "# " + ("Stellenanzeige" if is_de else "Job Advertisement")

    location_parts = [
        str(_compose_field_value("location.primary_city") or "").strip(),
        str(_compose_field_value("location.country") or "").strip(),
    ]
    location_text = ", ".join([part for part in location_parts if part])

    role_summary_value: str | None = None
    filtered_entries: list[tuple[str, str, str, str | list[str]]] = []
    for entry in entries:
        key, group, label, value = entry
        if key == "position.role_summary":
            if isinstance(value, list):
                role_summary_value = " ".join(value)
            else:
                role_summary_value = str(value)
            continue
        if key == "position.job_title":
            continue
        if key in {"location.primary_city", "location.country"} and location_text:
            continue
        filtered_entries.append(entry)

    group_order = [
        "basic",
        "company",
        "requirements",
        "employment",
        "compensation",
        "process",
    ]

    grouped: dict[str, list[tuple[str, str, str | list[str]]]] = {}
    for key, group, label, value in filtered_entries:
        grouped.setdefault(group, []).append((key, label, value))

    def _tr(text_de: str, text_en: str) -> str:
        return text_de if is_de else text_en

    tone_value = (tone or "").strip()
    raw_brand_keywords = _value_override("company.brand_keywords")
    if raw_brand_keywords in (None, "", []):
        raw_brand_keywords = _resolve("company.brand_keywords")
    if isinstance(raw_brand_keywords, list):
        brand_keywords_value: str | list[str] = [
            str(item).strip() for item in raw_brand_keywords if str(item).strip()
        ]
    elif isinstance(raw_brand_keywords, str):
        brand_keywords_value = raw_brand_keywords.strip()
    elif raw_brand_keywords is None:
        brand_keywords_value = ""
    else:
        brand_keywords_value = str(raw_brand_keywords).strip()

    structured_sections: list[dict[str, Any]] = []
    for group in group_order:
        section_entries = grouped.get(group, [])
        if not section_entries:
            continue
        section_payload: list[dict[str, Any]] = []
        for _key, label, value in section_entries:
            entry_payload: dict[str, Any] = {"label": label}
            if isinstance(value, list):
                items = [str(item).strip() for item in value if str(item).strip()]
                if not items:
                    continue
                entry_payload["items"] = items
            else:
                text_value = str(value).strip()
                if not text_value:
                    continue
                entry_payload["text"] = text_value
            section_payload.append(entry_payload)
        if not section_payload:
            continue
        structured_sections.append(
            {
                "group": group,
                "title": group_labels.get(group, group.title()),
                "entries": section_payload,
            }
        )

    brand_keywords_text = (
        ", ".join(brand_keywords_value)
        if isinstance(brand_keywords_value, list)
        else str(brand_keywords_value).strip()
    )

    if audience_text:
        cta_text = _tr(
            f"Fühlst du dich angesprochen ({audience_text})? Bewirb dich jetzt – wir freuen uns auf dich!",
            f"Does this sound like you ({audience_text})? Apply now – we'd love to hear from you!",
        )
    else:
        cta_text = _tr(
            "Bereit für den nächsten Schritt? Bewirb dich jetzt – wir freuen uns auf dich!",
            "Ready for the next step? Apply now – we'd love to hear from you!",
        )

    structured_payload: dict[str, Any] = {
        "language": lang_code,
        "audience": audience_text,
        "tone": tone_value,
        "style_reference": (style_reference or "").strip(),
        "heading": heading,
        "job_title": job_title_value,
        "company": {
            "display_name": company_display,
            "brand_name": company_brand,
            "legal_name": company_name,
        },
        "location": location_text,
        "summary": role_summary_value or "",
        "sections": structured_sections,
        "manual_sections": manual_sections_payload,
        "brand_keywords": brand_keywords_value,
        "cta_hint": cta_text,
    }

    document_lines: list[str] = [heading]
    if location_text:
        document_lines.append(
            f"**{_tr('Standort', 'Location')}:** {location_text}"
        )
    document_lines.append(
        f"*{_tr('Zielgruppe', 'Target audience')}: {audience_text}*"
    )
    meta_bits: list[str] = []
    if tone_value:
        tone_labels = {
            "formal": _tr("Formell", "Formal"),
            "casual": _tr("Locker", "Casual"),
            "creative": _tr("Kreativ", "Creative"),
            "diversity_focused": _tr("Diversität im Fokus", "Diversity-focused"),
        }
        tone_display = tone_labels.get(
            tone_value,
            tone_value.replace("_", " ").title(),
        )
        meta_bits.append(f"{_tr('Ton', 'Tone')}: {tone_display}")
    if brand_keywords_text:
        meta_bits.append(
            f"{_tr('Brand-Keywords', 'Brand keywords')}: {brand_keywords_text}"
        )
    if meta_bits:
        document_lines.append(f"*{' | '.join(meta_bits)}*")
    style_note = (style_reference or "").strip()
    if style_note:
        document_lines.append(
            f"*{_tr('Stilhinweis', 'Style note')}: {style_note}*"
        )
    if role_summary_value:
        document_lines.append("")
        document_lines.append(role_summary_value)

    for section in structured_sections:
        entries_payload = section.get("entries", [])
        if not entries_payload:
            continue
        document_lines.append("")
        document_lines.append(f"## {section.get('title', '')}")
        for entry_payload in entries_payload:
            label = str(entry_payload.get("label") or "").strip()
            items = entry_payload.get("items") or []
            text_value = str(entry_payload.get("text") or "").strip()
            if items:
                if not label:
                    label = _tr("Details", "Details")
                document_lines.append(f"**{label}:**")
                for item in items:
                    if item:
                        document_lines.append(f"- {item}")
            elif label or text_value:
                content = text_value if label else text_value
                if label and content:
                    document_lines.append(f"**{label}:** {content}")
                elif label:
                    document_lines.append(f"**{label}:**")
                else:
                    document_lines.append(content)
            if document_lines and document_lines[-1] != "":
                document_lines.append("")
        if document_lines and document_lines[-1] == "":
            document_lines.pop()

    if manual_sections_payload:
        document_lines.append("")
        document_lines.append(
            f"## {_tr('Zusätzliche Hinweise', 'Additional notes')}"
        )
        for entry in manual_sections_payload:
            title = entry.get("title", "")
            content = entry.get("content", "")
            if title:
                document_lines.append(f"**{title}:**")
                document_lines.append(content)
            else:
                document_lines.append(content)
            document_lines.append("")
        if document_lines and document_lines[-1] == "":
            document_lines.pop()

    if cta_text:
        document_lines.append("")
        document_lines.append(cta_text)

    document = "\n".join(document_lines).strip()

    if model is None:
        model = get_model_for(ModelTask.JOB_AD)
    try:
        messages = build_job_ad_prompt(structured_payload)
        response = api.call_chat_api(
            messages,
            model=model,
            temperature=0.7,
            max_tokens=900,
        )
        llm_output = _chat_content(response).strip()
    except Exception:
        llm_output = ""

    return llm_output or document


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
