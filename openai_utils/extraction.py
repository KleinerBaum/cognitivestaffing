"""High-level extraction and suggestion helpers built on the OpenAI API."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from config import ModelTask, VECTOR_STORE_ID, get_model_for
from core.job_ad import JOB_AD_FIELDS, JOB_AD_GROUP_LABELS, iter_field_keys
from llm.prompts import build_job_ad_prompt
from llm.rag_pipeline import (
    FieldExtractionContext,
    RetrievedChunk,
    build_global_context as default_global_context,
)
from models.interview_guide import (
    InterviewGuide,
    InterviewGuideFocusArea,
    InterviewGuideMetadata,
    InterviewGuideQuestion,
)
from utils.i18n import tr
from . import api
from .api import _chat_content
from .tools import build_extraction_tool

try:  # pragma: no cover - Streamlit not required for CLI usage
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    st = None  # type: ignore[assignment]

_GENDER_MARKER_RE = re.compile(
    r"(?:\((?:[mwdgfxnai]\s*/\s*){1,4}[mwdgfxnai]\)"
    r"|\((?:gn\*?|div|x|all genders|alle geschlechter)\)"
    r"|all genders|alle geschlechter)",
    re.IGNORECASE,
)


def _contains_gender_marker(text: str, extra_markers: Sequence[str] | None = None) -> bool:
    """Return ``True`` if ``text`` already includes an inclusive gender marker."""

    if not text:
        return False
    if _GENDER_MARKER_RE.search(text):
        return True
    if not extra_markers:
        return False
    lowered = text.casefold()
    for marker in extra_markers:
        candidate = (marker or "").strip()
        if not candidate:
            continue
        if candidate.casefold() in lowered:
            return True
    return False


tracer = trace.get_tracer(__name__)


def _resolve_vector_store_id(candidate: str | None) -> str:
    """Return the active vector store ID based on runtime configuration."""

    if candidate:
        candidate = candidate.strip()
        if candidate:
            return candidate

    session_value: str | None = None
    if st is not None:
        try:
            raw_value = st.session_state.get("vector_store_id")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            raw_value = None
        if raw_value:
            session_value = str(raw_value).strip()
    for value in (session_value, (VECTOR_STORE_ID or "").strip()):
        if value:
            return value
    return ""


def extract_company_info(
    text: str,
    model: str | None = None,
    *,
    vector_store_id: str | None = None,
) -> dict:
    """Extract company details from website text using OpenAI."""

    with tracer.start_as_current_span("llm.extract_company_info") as span:
        text = text.strip()
        if not text:
            span.set_status(Status(StatusCode.ERROR, "empty_input"))
            return {}
        if model is None:
            model = get_model_for(ModelTask.COMPANY_INFO)
        span.set_attribute("llm.model", model)

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
        store_id = _resolve_vector_store_id(vector_store_id)
        tools: list[dict[str, Any]] = []
        tool_choice: str | None = None
        if store_id:
            tools.append({"type": "file_search", "vector_store_ids": [store_id]})
            tool_choice = "auto"
        else:
            tools.append({"type": "web_search"})
        span.set_attribute("llm.vector_store", bool(store_id))
        span.set_attribute("llm.tools", ",".join(tool["type"] for tool in tools))
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
                task=ModelTask.COMPANY_INFO,
                tools=tools,
                tool_choice=tool_choice,
            )
            data = json.loads(_chat_content(res))
        except Exception as exc:  # pragma: no cover - network/SDK issues
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "api_error"))
            data = {}

        result: dict[str, str] = {}
        if isinstance(data, dict):
            for key in expected_fields:
                val = data.get(key, "")
                if isinstance(val, str):
                    val = val.strip()
                if val:
                    result[key] = val
        span.set_attribute("extraction.company_fields", len(result))
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
        if result:
            span.add_event("fallback_keyword_extraction")
            span.set_attribute("extraction.company_fields", len(result))
        return result


FUNCTION_NAME = "cognitive_needs_extract"


@dataclass(slots=True)
class ExtractionResult:
    """Structured result returned by :func:`extract_with_function`."""

    data: Mapping[str, Any]
    field_contexts: Mapping[str, FieldExtractionContext]
    global_context: Sequence[RetrievedChunk]


def _extract_tool_arguments(result: api.ChatCallResult) -> str | None:
    """Return the raw tool payload from the first call, preferring ``input``."""

    for call in result.tool_calls or []:
        func = call.get("function") if isinstance(call, dict) else None
        if func is None and isinstance(call, dict):
            func = {
                "arguments": call.get("arguments"),
                "input": call.get("input"),
            }
        if not func:
            continue
        payload = func.get("input")
        if payload is None:
            payload = func.get("arguments")
        if isinstance(payload, str):
            text = payload.strip()
            if text:
                return text
        elif payload is not None:
            try:
                return json.dumps(payload)
            except TypeError:
                continue
    return None


def _parse_json_object(payload: Any) -> dict[str, Any]:
    """Return ``payload`` parsed as a JSON object without heuristics."""

    if isinstance(payload, Mapping):
        data = dict(payload)
    elif isinstance(payload, str):
        text = payload.strip()
        if not text:
            raise ValueError("Structured extraction payload is empty.")
        data = json.loads(text)
    else:
        raise ValueError("Structured extraction payload must be JSON text or mapping.")

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

    Structured responses must be valid JSON objects. Any malformed payload will
    raise a ``ValueError`` before validation against the ``NeedAnalysisProfile``
    schema.
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
            "You are a vacancy extraction engine applying GPT-5 prompting discipline. "
            "Start by silently planning how you will align the retrieved snippets to "
            "each schema field—do not output the plan. Execute the plan step by step, "
            "persisting until every field is processed. Do not stop until the user's "
            "request is fully satisfied. Use the provided global context and the "
            "per-field snippets to populate the vacancy schema by calling the function "
            f"{FUNCTION_NAME}. If no relevant snippet is provided for a field, return "
            "an empty string or empty list. Do not invent data."
        )
        user_payload = json.dumps(payload, ensure_ascii=False)
        messages: Sequence[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ]
    else:
        system_prompt = (
            "You are a vacancy extraction engine operating under GPT-5 best practices. "
            "Mentally plan how you will parse the text, map it to schema keys, and "
            "validate the result—never output the plan. Follow the plan meticulously, "
            "step by step, and do not stop until the user's request is completely resolved. "
            "Analyse the job advertisement and return the structured vacancy profile "
            f"by calling the provided function {FUNCTION_NAME}. Do not return free-form text."
        )
        user_payload = job_text
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ]

    response = api.call_chat_api(
        messages,
        model=model,
        temperature=0.0,
        tools=build_extraction_tool(FUNCTION_NAME, schema, allow_extra=False),
        tool_choice={
            "type": "function",
            "function": {"name": FUNCTION_NAME},
        },
        task=ModelTask.EXTRACTION,
    )

    arguments = _extract_tool_arguments(response)
    if not arguments:
        # Some models ignore the tool request and emit plain text. Retry forcing
        # JSON mode to keep the pipeline deterministic.
        retry_messages: list[dict[str, str]] = []
        for index, message in enumerate(messages):
            updated = dict(message)
            if index == 0:
                updated["content"] = (
                    f"{message.get('content', '')} Return only valid JSON that conforms exactly to the provided schema."
                )
            retry_messages.append(updated)
        if not retry_messages:
            retry_messages = [
                {
                    "role": "system",
                    "content": ("Return only valid JSON that conforms exactly to the provided schema."),
                },
                {"role": "user", "content": user_payload},
            ]
        second = api.call_chat_api(
            retry_messages,
            model=model,
            temperature=0.0,
            json_schema={"name": FUNCTION_NAME, "schema": schema},
            max_tokens=1200,
            task=ModelTask.EXTRACTION,
            previous_response_id=response.response_id,
        )
        arguments = _chat_content(second)

    if not arguments or not str(arguments).strip():
        raise RuntimeError("Extraction failed: no structured data received from LLM.")

    try:
        raw = _parse_json_object(arguments)
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
        task=ModelTask.SKILL_SUGGESTION,
    )
    answer = _chat_content(res)
    tech_skills: list[str] = []
    soft_skills: list[str] = []
    try:
        data = json.loads(answer)
        if isinstance(data, dict):
            tech_skills = [str(s).strip() for s in data.get("technical", []) if str(s).strip()]
            soft_skills = [str(s).strip() for s in data.get("soft", []) if str(s).strip()]
    except Exception:
        bucket = "tech"
        for line in answer.splitlines():
            skill = line.strip("-•* \t")
            if not skill:
                continue
            if skill.lower().startswith("soft"):
                bucket = "soft"
                continue
            if skill.lower().startswith("technical") or skill.lower().startswith("technische"):
                bucket = "tech"
                continue
            if bucket == "tech":
                tech_skills.append(skill)
            else:
                soft_skills.append(skill)
    # Normalize skill labels locally and drop duplicates against existing skills
    try:
        from core.esco_utils import normalize_skills

        existing_norm = {s.lower() for s in normalize_skills(existing_skills, lang=lang)}
        tech_skills = [s for s in normalize_skills(tech_skills, lang=lang) if s.lower() not in existing_norm]
        soft_skills = [s for s in normalize_skills(soft_skills, lang=lang) if s.lower() not in existing_norm]
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
    focus_terms: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Suggest tools, skills, and certificates for a job title.

    Args:
        job_title: Target role title.
        lang: Output language ("en" or "de").
        model: Optional OpenAI model override.
        focus_terms: Optional categories the AI should emphasise.

    Returns:
        Dict with keys ``tools_and_technologies``, ``hard_skills``,
        ``soft_skills`` and ``certificates`` each containing up to 12 suggestions.
    """

    job_title = job_title.strip()
    if not job_title:
        return {
            "tools_and_technologies": [],
            "hard_skills": [],
            "soft_skills": [],
            "certificates": [],
        }
    if model is None:
        model = get_model_for(ModelTask.SKILL_SUGGESTION)

    focus_terms = [str(term).strip() for term in (focus_terms or []) if str(term).strip()]

    if lang.startswith("de"):
        prompt = (
            "Gib exakt 12 IT-Technologien, 12 Hard Skills, 12 Soft Skills und 12 "
            "relevante Zertifikate für den Jobtitel "
            f"'{job_title}'. Antworte als JSON mit den Schlüsseln "
            "'tools_and_technologies', 'hard_skills', 'soft_skills' und "
            "'certificates'."
        )
        if focus_terms:
            prompt += " Berücksichtige diese Schwerpunkte bei der Auswahl: " + ", ".join(focus_terms) + "."
    else:
        prompt = (
            "List exactly 12 IT technologies, 12 hard skills, 12 soft skills, "
            "and 12 relevant certificates for the job title "
            f"'{job_title}'. Respond with JSON using the keys "
            "'tools_and_technologies', 'hard_skills', 'soft_skills', and "
            "'certificates'."
        )
        if focus_terms:
            prompt += " Prioritise options connected to: " + ", ".join(focus_terms) + "."

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
                    "certificates": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "tools_and_technologies",
                    "hard_skills",
                    "soft_skills",
                    "certificates",
                ],
                "additionalProperties": False,
            },
        },
        max_tokens=400,
        task=ModelTask.SKILL_SUGGESTION,
    )
    raw = _chat_content(res)
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    def _clean(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        cleaned = [str(it).strip() for it in items if isinstance(it, str) and it.strip()]
        return cleaned[:12]

    tools = _clean(data.get("tools_and_technologies"))
    hard = _clean(data.get("hard_skills"))
    soft = _clean(data.get("soft_skills"))
    certificates = _clean(data.get("certificates"))

    try:  # Normalize skill labels locally
        from core.esco_utils import normalize_skills

        tools = normalize_skills(tools, lang=lang)
        hard = normalize_skills(hard, lang=lang)
        soft = normalize_skills(soft, lang=lang)
        certificates = normalize_skills(certificates, lang=lang)
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
        "certificates": _unique(certificates),
    }


def suggest_benefits(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
    model: str | None = None,
    *,
    focus_areas: Sequence[str] | None = None,
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
    focus_areas = [str(area).strip() for area in (focus_areas or []) if str(area).strip()]
    if lang.startswith("de"):
        prompt = f"Nenne bis zu 5 Vorteile oder Zusatzleistungen, die für eine Stelle als {job_title} üblich sind"
        if industry:
            prompt += f" in der Branche {industry}"
        prompt += ". Antworte als JSON-Liste und vermeide Vorteile, die bereits in der Liste unten stehen.\n"
        if existing_benefits:
            prompt += f"Bereits aufgelistet: {existing_benefits}"
        if focus_areas:
            prompt += " Betone folgende Kategorien besonders: " + ", ".join(focus_areas) + "."
    else:
        prompt = f"List up to 5 benefits or perks commonly offered for a {job_title} role"
        if industry:
            prompt += f" in the {industry} industry"
        prompt += ". Respond as a JSON array and avoid mentioning any benefit already listed below.\n"
        if existing_benefits:
            prompt += f"Already listed: {existing_benefits}"
        if focus_areas:
            prompt += " Emphasise the following categories: " + ", ".join(focus_areas) + "."
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
        task=ModelTask.BENEFIT_SUGGESTION,
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


def suggest_role_tasks(job_title: str, num_tasks: int = 5, model: str | None = None) -> list[str]:
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
        task=ModelTask.TASK_SUGGESTION,
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
            "Du bist ein HR-Experte. Plane gedanklich deine Vorgehensweise (nicht ausgeben) und arbeite die Schritte nacheinander ab, bis die Anfrage vollständig erfüllt ist. "
            "Entwickle fünf kurze, konkrete Vorschläge für den Onboarding-Prozess einer neuen Fachkraft."
        )
        prompt += f"\nRolle: {job_title}."
        if company_name:
            prompt += f"\nUnternehmen: {company_name}."
        if industry:
            prompt += f"\nBranche: {industry}."
        if culture:
            prompt += f"\nUnternehmenskultur oder Werte: {culture}."
        prompt += (
            "\nFolge diesen Schritten: 1) Kontext prüfen, 2) passende Maßnahmen auswählen, 3) Vorschläge präzise formulieren, 4) Vollständigkeit sicherstellen."
            "\nJeder Vorschlag sollte eine eigenständige Maßnahme mit Fokus auf Kommunikation, Wissensaufbau oder Integration sein."
            "\nFormatiere die Ausgabe als JSON-Array mit genau fünf String-Elementen."
        )
    else:
        prompt = (
            "You are an HR expert. Silently outline your approach (do not output it), execute each step sequentially, and do not stop until the request is completely satisfied. "
            "Devise five concise, actionable onboarding initiatives for a new hire."
        )
        prompt += f"\nRole: {job_title}."
        if company_name:
            prompt += f"\nCompany: {company_name}."
        if industry:
            prompt += f"\nIndustry: {industry}."
        if culture:
            prompt += f"\nCompany culture or values: {culture}."
        prompt += (
            "\nFollow these steps: 1) Review the context, 2) choose relevant activities, 3) articulate each initiative clearly, 4) confirm all five slots are filled."
            "\nEach suggestion should describe a single activity focusing on communication, knowledge transfer, or integration."
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
        task=ModelTask.ONBOARDING_SUGGESTION,
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

    if not isinstance(suggestions_payload, Sequence) or isinstance(suggestions_payload, (str, bytes)):
        suggestions_payload = []

    try:
        suggestions = [str(item).strip() for item in suggestions_payload if str(item).strip()]
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


def _normalise_guide_list(payload: Sequence[str] | str) -> list[str]:
    """Normalise skill/responsibility inputs into a list of trimmed strings."""

    if isinstance(payload, str):
        items = [part.strip() for part in payload.replace("\r", "").splitlines()]
    else:
        items = [str(item).strip() for item in payload]
    return [item for item in items if item]


def _sentence_case(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _build_deterministic_interview_guide(
    *,
    job_title: str,
    responsibilities_list: list[str],
    hard_list: list[str],
    soft_list: list[str],
    audience: str,
    num_questions: int,
    lang: str,
    culture_note: str,
    tone_text: str,
) -> InterviewGuide:
    """Return a deterministic interview guide used as an offline fallback."""

    lang_code = (lang or "de").lower()
    is_de = lang_code.startswith("de")

    def _tr(value_de: str, value_en: str) -> str:
        return value_de if is_de else value_en

    audience_display = {
        "general": _tr("Allgemeines Interviewteam", "General interview panel"),
        "technical": _tr("Technisches Interviewteam", "Technical panel"),
        "leadership": _tr("Führungsteam", "Leadership panel"),
    }.get(audience, audience)

    job_title_text = job_title.strip() or _tr("diese Position", "this role")

    def _make_question(question: str, focus: str, evaluation: str) -> InterviewGuideQuestion:
        return InterviewGuideQuestion(
            question=_sentence_case(question),
            focus=focus.strip(),
            evaluation=evaluation.strip(),
        )

    questions: list[InterviewGuideQuestion] = []

    def _add_question(entry: InterviewGuideQuestion) -> None:
        max_questions = max(3, min(10, num_questions))
        if len(questions) >= max_questions:
            return
        key = entry.question.strip().lower()
        if key in {existing.question.strip().lower() for existing in questions}:
            return
        questions.append(entry)

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
    _add_question(motivation_question)

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
        _add_question(
            _make_question(
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
        )

    for skill in hard_list[:4]:
        _add_question(
            _make_question(
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
        )

    for skill in soft_list[:3]:
        _add_question(
            _make_question(
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
        )

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
            _add_question(
                _make_question(
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
            )
            if len(questions) >= num_questions:
                break

    if len(questions) > num_questions:
        questions = questions[:num_questions]

    focus_areas: list[InterviewGuideFocusArea] = []
    if responsibilities_list:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Schlüsselaufgaben", "Key responsibilities"),
                items=responsibilities_list[:5],
            )
        )
    if hard_list:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Kernkompetenzen", "Core hard skills"),
                items=hard_list[:5],
            )
        )
    if soft_list:
        focus_areas.append(
            InterviewGuideFocusArea(
                label=_tr("Soft Skills", "Soft skills"),
                items=soft_list[:5],
            )
        )

    evaluation_notes = [
        _tr(
            "Bewerte Klarheit und Struktur der Antworten. Fordere Nachfragen, wenn Beispiele fehlen.",
            "Assess clarity and structure of answers. Ask follow-ups when examples are missing.",
        ),
        _tr(
            "Bitte um konkrete Resultate, Kennzahlen oder Lernerfahrungen, um Impact zu verifizieren.",
            "Request concrete outcomes, metrics, or learnings to verify impact.",
        ),
        _tr(
            "Vergleiche Antworten mit dem gewünschten Ton und Kulturfit der Organisation.",
            "Check answers against the desired tone and cultural fit of the organisation.",
        ),
    ]
    if culture_note:
        evaluation_notes.append(
            _tr(
                "Achte besonders auf Hinweise zur beschriebenen Unternehmenskultur.",
                "Pay special attention to alignment with the described company culture.",
            )
        )

    metadata = InterviewGuideMetadata(
        language="de" if is_de else "en",
        heading=(_tr("Interviewleitfaden", "Interview Guide") + f" – {job_title_text}"),
        job_title=job_title_text,
        audience=audience,
        audience_label=audience_display,
        tone=tone_text,
        culture_note=culture_note or None,
    )

    guide = InterviewGuide(
        metadata=metadata,
        focus_areas=focus_areas,
        questions=questions,
        evaluation_notes=evaluation_notes,
    )
    return guide.ensure_markdown()


def _prepare_interview_guide_payload(
    *,
    job_title: str,
    responsibilities: str,
    hard_skills: Sequence[str] | str,
    soft_skills: Sequence[str] | str,
    audience: str,
    num_questions: int,
    lang: str,
    company_culture: str,
    tone: str | None,
) -> tuple[dict[str, Any], InterviewGuide]:
    """Prepare payload for prompting and a deterministic fallback."""

    hard_list = _normalise_guide_list(hard_skills)
    soft_list = _normalise_guide_list(soft_skills)
    responsibilities_list = _normalise_guide_list(responsibilities)

    tone_text = tone.strip() if isinstance(tone, str) else ""
    lang_code = (lang or "de").lower()
    is_de = lang_code.startswith("de")
    if not tone_text:
        tone_text = tr(
            "professionell und strukturiert",
            "professional and structured",
            "de" if is_de else "en",
        )

    culture_note = company_culture.strip()

    fallback = _build_deterministic_interview_guide(
        job_title=job_title,
        responsibilities_list=responsibilities_list,
        hard_list=hard_list,
        soft_list=soft_list,
        audience=audience,
        num_questions=num_questions,
        lang=lang,
        culture_note=culture_note,
        tone_text=tone_text,
    )

    payload: dict[str, Any] = {
        "language": "de" if is_de else "en",
        "job_title": job_title,
        "requested_questions": max(3, min(10, num_questions)),
        "audience": audience,
        "audience_display": fallback.metadata.audience_label,
        "tone": tone_text,
        "company_culture": culture_note,
        "responsibilities": responsibilities_list,
        "hard_skills": hard_list,
        "soft_skills": soft_list,
        "seed_focus_areas": [area.model_dump() for area in fallback.focus_areas],
        "sample_questions": [question.model_dump() for question in fallback.questions[: max(3, min(6, num_questions))]],
        "evaluation_note_examples": list(fallback.evaluation_notes),
    }

    return payload, fallback


def _build_interview_guide_prompt(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return chat messages guiding the model to produce an interview guide."""

    lang = str(payload.get("language") or "de").lower()

    system_msg = tr(
        "Du bist eine erfahrene HR-Coachin, die strukturierte Interviewleitfäden erstellt. Plane deine Schritte kurz im Kopf (nicht ausgeben), führe sie nacheinander aus und brich erst ab, wenn alle Anforderungen erfüllt sind.",
        "You are an experienced HR coach who designs structured interview guides. Plan your steps briefly in your head (do not output them), execute them sequentially, and do not stop until every requirement is met.",
        lang,
    )

    instruction_lines = [
        tr(
            "Erstelle eine strukturierte Liste von Interviewfragen mit Bewertungsleitfaden.",
            "Create a structured list of interview questions with evaluation guidance.",
            lang,
        ),
        tr(
            "Arbeite strikt nach diesen Schritten: 1) Kontext prüfen, 2) Fragenbereiche planen, 3) Fragen mit Bewertung ausformulieren, 4) JSON gegen das Schema prüfen.",
            "Follow these steps strictly: 1) Review the context, 2) plan the question coverage, 3) draft questions with scoring guidance, 4) validate the JSON against the schema.",
            lang,
        ),
        tr(
            "Nutze die bereitgestellten Aufgaben, Skills und kulturellen Hinweise als Kontext.",
            "Use the provided responsibilities, skills, and culture notes as context.",
            lang,
        ),
        tr(
            "Stelle sicher, dass mindestens eine Frage zu Verantwortlichkeiten, Hard Skills, Soft Skills und – falls vorhanden – Unternehmenskultur gestellt wird.",
            "Ensure there is at least one question covering responsibilities, hard skills, soft skills, and company culture when provided.",
            lang,
        ),
        tr(
            "Beziehe dich in jeder Frage ausdrücklich auf die Stellenbezeichnung und Seniorität aus dem Kontext.",
            "Explicitly reference the provided job title and seniority context in every question.",
            lang,
        ),
        tr(
            "Passe Ton und Zielgruppe an und halte dich an die gewünschte Fragenanzahl.",
            "Match the requested tone and audience and respect the desired question count.",
            lang,
        ),
        tr(
            "Füge 3-5 allgemeine Bewertungshinweise als Liste 'evaluation_notes' hinzu.",
            "Provide 3-5 general evaluation notes in the 'evaluation_notes' list.",
            lang,
        ),
        tr(
            "Liefere ausschließlich JSON, das exakt dem angegebenen Schema entspricht.",
            "Return only JSON that exactly matches the provided schema.",
            lang,
        ),
    ]

    context_json = json.dumps(payload, ensure_ascii=False, indent=2)
    user_message = "\n".join(instruction_lines) + "\n\nContext:\n```json\n" + context_json + "\n```"

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_message},
    ]


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
    vector_store_id: str | None = None,
    model: str | None = None,
) -> InterviewGuide:
    """Create an interview guide via the LLM with a deterministic fallback."""

    payload, fallback = _prepare_interview_guide_payload(
        job_title=job_title,
        responsibilities=responsibilities,
        hard_skills=hard_skills,
        soft_skills=soft_skills,
        audience=audience,
        num_questions=num_questions,
        lang=lang,
        company_culture=company_culture,
        tone=tone,
    )

    if model is None:
        model = get_model_for(ModelTask.INTERVIEW_GUIDE)

    store_id = _resolve_vector_store_id(vector_store_id)
    tools: list[dict[str, Any]] = []
    tool_choice: str | None = None
    if store_id:
        tools = [{"type": "file_search", "vector_store_ids": [store_id]}]
        tool_choice = "auto"

    try:
        messages = _build_interview_guide_prompt(payload)
        schema = InterviewGuide.model_json_schema()
        response = api.call_chat_api(
            messages,
            model=model,
            temperature=0.6,
            max_tokens=900,
            json_schema={"name": "interviewGuide", "schema": schema},
            task=ModelTask.INTERVIEW_GUIDE,
            tools=tools or None,
            tool_choice=tool_choice,
        )
        data = _parse_json_object(_chat_content(response))
        guide = InterviewGuide.model_validate(data).ensure_markdown()
        return guide
    except Exception:
        return fallback


def _prepare_job_ad_payload(
    session_data: Mapping[str, Any],
    selected_fields: Sequence[str],
    *,
    target_audience: str,
    manual_sections: Sequence[Mapping[str, str]] | None = None,
    style_reference: str | None = None,
    tone: str | None = None,
    lang: str | None = None,
    selected_values: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Build prompt payload and Markdown fallback for job ad generation."""

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
    group_labels = {key: (labels[0] if is_de else labels[1]) for key, labels in JOB_AD_GROUP_LABELS.items()}

    def _resolve(path: str) -> Any:
        if path in data:
            return data[path]
        cursor: Any = data
        for part in path.split("."):
            if isinstance(cursor, Mapping) and part in cursor:
                cursor = cursor[part]
            else:
                return None
        return cursor

    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            items = [part.strip() for part in value.replace("\r", "").splitlines() if part.strip()]
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
        "requirements.certificates",
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
            suffix = key[len(prefix) :]
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
    gender_markers: list[str] = []

    if is_de and job_title_value:
        marker_keys = [
            "job_ad.gender_inclusive_token",
            "job_ad.gender_marker",
            "job_ad.gender_suffix",
            "position.gender_inclusive_token",
            "position.gender_marker",
            "position.gender_suffix",
            "meta.gender_marker",
        ]

        seen_markers: set[str] = set()
        for marker_key in marker_keys:
            for source in (_value_override(marker_key), _resolve(marker_key)):
                if not source:
                    continue
                if isinstance(source, str):
                    candidate = source.strip()
                    if candidate:
                        lowered = candidate.casefold()
                        if lowered not in seen_markers:
                            seen_markers.add(lowered)
                            gender_markers.append(candidate)
                elif isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
                    for item in source:
                        candidate = str(item).strip()
                        if not candidate:
                            continue
                        lowered = candidate.casefold()
                        if lowered in seen_markers:
                            continue
                        seen_markers.add(lowered)
                        gender_markers.append(candidate)

        if not _contains_gender_marker(job_title_value, gender_markers):
            marker_to_use = gender_markers[0] if gender_markers else "(m/w/d)"
            job_title_value = f"{job_title_value} {marker_to_use}".strip()

    company_brand = _compose_field_value("company.brand_name") or ""
    company_name = _compose_field_value("company.name") or ""
    company_display = company_brand or company_name

    if job_title_value and company_display:
        heading = f"# {job_title_value} bei {company_display}" if is_de else f"# {job_title_value} at {company_display}"
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
        brand_keywords_value: str | list[str] = [str(item).strip() for item in raw_brand_keywords if str(item).strip()]
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
        ", ".join(brand_keywords_value) if isinstance(brand_keywords_value, list) else str(brand_keywords_value).strip()
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
        document_lines.append(f"**{_tr('Standort', 'Location')}:** {location_text}")
    document_lines.append(f"*{_tr('Zielgruppe', 'Target audience')}: {audience_text}*")
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
        meta_bits.append(f"{_tr('Brand-Keywords', 'Brand keywords')}: {brand_keywords_text}")
    if meta_bits:
        document_lines.append(f"*{' | '.join(meta_bits)}*")
    style_note = (style_reference or "").strip()
    if style_note:
        document_lines.append(f"*{_tr('Stilhinweis', 'Style note')}: {style_note}*")
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
        document_lines.append(f"## {_tr('Zusätzliche Hinweise', 'Additional notes')}")
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

    return structured_payload, document


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
    vector_store_id: str | None = None,
) -> str:
    """Generate a structured job advertisement from collected profile data."""

    structured_payload, document = _prepare_job_ad_payload(
        session_data,
        selected_fields,
        target_audience=target_audience,
        manual_sections=manual_sections,
        style_reference=style_reference,
        tone=tone,
        lang=lang,
        selected_values=selected_values,
    )

    if model is None:
        model = get_model_for(ModelTask.JOB_AD)

    store_id = _resolve_vector_store_id(vector_store_id)
    tools: list[dict[str, Any]] = []
    tool_choice: str | None = None
    if store_id:
        tools = [{"type": "file_search", "vector_store_ids": [store_id]}]
        tool_choice = "auto"
    try:
        messages = build_job_ad_prompt(structured_payload)
        response = api.call_chat_api(
            messages,
            model=model,
            temperature=0.7,
            max_tokens=900,
            task=ModelTask.JOB_AD,
            tools=tools or None,
            tool_choice=tool_choice,
        )
        llm_output = _chat_content(response).strip()
    except Exception:
        llm_output = ""

    return llm_output or document


def stream_job_ad(
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
    vector_store_id: str | None = None,
) -> tuple[api.ChatStream, str]:
    """Return a streaming iterator and fallback document for job ad generation."""

    structured_payload, document = _prepare_job_ad_payload(
        session_data,
        selected_fields,
        target_audience=target_audience,
        manual_sections=manual_sections,
        style_reference=style_reference,
        tone=tone,
        lang=lang,
        selected_values=selected_values,
    )

    if model is None:
        model = get_model_for(ModelTask.JOB_AD)

    store_id = _resolve_vector_store_id(vector_store_id)
    if store_id:
        raise RuntimeError("Job ad streaming with retrieval is not supported.")

    messages = build_job_ad_prompt(structured_payload)
    stream = api.stream_chat_api(
        messages,
        model=model,
        temperature=0.7,
        max_tokens=900,
        task=ModelTask.JOB_AD,
    )
    return stream, document


def summarize_company_page(
    text: str,
    section: str,
    *,
    lang: str = "de",
    model: str | None = None,
) -> str:
    """Summarize a company web page into a concise paragraph."""

    with tracer.start_as_current_span("documents.summarize_company_page") as span:
        cleaned = text.strip()
        if not cleaned:
            span.set_status(Status(StatusCode.ERROR, "empty_input"))
            return ""
        if len(cleaned) > 8000:
            cleaned = cleaned[:8000]
        if model is None:
            model = get_model_for(ModelTask.EXPLANATION)
        span.set_attribute("llm.model", model)
        span.set_attribute("document.section", section)
        span.set_attribute("document.lang", lang)

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
                api.call_chat_api(
                    messages,
                    model=model,
                    temperature=0.2,
                    max_tokens=220,
                    task=ModelTask.EXPLANATION,
                )
            ).strip()
        except Exception as exc:  # pragma: no cover - network/SDK issues
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "api_error"))
            summary = ""

        if summary:
            span.set_attribute("document.summary_length", len(summary))
            return summary

        fallback = textwrap.shorten(cleaned, width=420, placeholder="…")
        span.add_event("fallback_summary")
        return fallback


def refine_document(original: str, feedback: str, model: str | None = None) -> str:
    """Adjust a generated document using user feedback."""

    with tracer.start_as_current_span("documents.refine_document") as span:
        if model is None:
            model = get_model_for(ModelTask.DOCUMENT_REFINEMENT)
        span.set_attribute("llm.model", model)
        span.set_attribute("document.feedback_length", len(feedback or ""))

        prompt = (
            "Revise the following document based on the user instructions.\n"
            f"Document:\n{original}\n\n"
            f"Instructions: {feedback}"
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            refined = _chat_content(
                api.call_chat_api(
                    messages,
                    model=model,
                    temperature=0.7,
                    max_tokens=800,
                    task=ModelTask.DOCUMENT_REFINEMENT,
                )
            )
        except Exception as exc:  # pragma: no cover - network/SDK issues
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "api_error"))
            return original

        span.set_attribute("document.refined_length", len(refined))
        return refined


def what_happened(
    session_data: dict,
    output: str,
    doc_type: str = "document",
    model: str | None = None,
) -> str:
    """Explain how a document was generated and which keys were used."""

    with tracer.start_as_current_span("documents.explain_document") as span:
        if model is None:
            model = get_model_for(ModelTask.EXPLANATION)
        span.set_attribute("llm.model", model)
        span.set_attribute("document.type", doc_type)
        keys_used = [k for k, v in session_data.items() if v]
        span.set_attribute("document.source_key_count", len(keys_used))
        prompt = (
            f"Explain how the following {doc_type} was generated using the keys: {', '.join(keys_used)}.\n"
            f"{doc_type.title()}:\n{output}"
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            explanation = _chat_content(
                api.call_chat_api(
                    messages,
                    model=model,
                    temperature=0.3,
                    max_tokens=300,
                    task=ModelTask.EXPLANATION,
                )
            )
        except Exception as exc:  # pragma: no cover - network/SDK issues
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "api_error"))
            return ""

        span.set_attribute("document.explanation_length", len(explanation))
        return explanation


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
    "stream_job_ad",
    "summarize_company_page",
    "refine_document",
    "what_happened",
]
