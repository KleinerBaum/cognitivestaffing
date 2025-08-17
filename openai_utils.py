# openai_utils.py 
from __future__ import annotations
import json, logging, httpx, backoff
import os
import re
from typing import Any, Dict, List, Optional, Sequence, cast
from dataclasses import dataclass
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from core.schema import VacalyserJD

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

logger = logging.getLogger("vacalyser.openai")

@dataclass
class ChatCallResult:
    content: Optional[str]
    tool_calls: list[dict]
    function_call: Optional[dict]
    usage: dict

class OpenAIClient:
    def __init__(self, api_key: str, base_url: str | None = None, timeout_s: int = 45):
        self._base = (base_url or "https://api.openai.com").rstrip("/")
        self._http = httpx.Client(timeout=timeout_s)
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def close(self):
        try: self._http.close()
        except Exception: pass

    @backoff.on_exception(backoff.expo, (httpx.HTTPError, TimeoutError), max_time=60)
    def chat(self, *, model: str, messages: Sequence[dict], temperature: float = 0.2,
             max_tokens: int | None = None, response_format: Optional[dict] = None,
             tools: Optional[list] = None, tool_choice: Optional[Any] = None,
             functions: Optional[list] = None, function_call: Optional[Any] = None,
             seed: Optional[int] = None, extra: Optional[dict] = None) -> ChatCallResult:

        payload = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None: payload["max_tokens"] = max_tokens
        if response_format: payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
            if tool_choice is not None: payload["tool_choice"] = tool_choice
        if functions is not None:
            payload["functions"] = functions
            if function_call is not None: payload["function_call"] = function_call
        if seed is not None: payload["seed"] = seed
        if extra: payload.update(extra)

        r = self._http.post(f"{self._base}/v1/chat/completions", headers=self._headers, json=payload)
        r.raise_for_status()
        data = r.json()
        ch = data["choices"][0]
        msg = ch.get("message", {})
        res = ChatCallResult(
            content=msg.get("content"),
            tool_calls=msg.get("tool_calls") or [],
            function_call=msg.get("function_call"),
            usage=data.get("usage", {}),
        )
        logger.debug("OpenAI usage: %s", res.usage)
        return res

_CLIENT: OpenAIClient | None = None

def get_client() -> OpenAIClient:
    global _CLIENT
    if _CLIENT is None:
        import os
        key = os.getenv("OPENAI_API_KEY") or ""
        if not key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        base = os.getenv("OPENAI_BASE_URL") or None
        _CLIENT = OpenAIClient(key, base_url=base)
    return _CLIENT

def call_chat_api(messages: Sequence[dict], *, model: str = "gpt-4o-mini",
                  temperature: float = 0.2, max_tokens: int | None = None,
                  json_strict: bool = False, tools: Optional[list] = None,
                  tool_choice: Optional[Any] = None,
                  functions: Optional[list] = None, function_call: Optional[Any] = None,
                  seed: Optional[int] = None, extra: Optional[dict] = None) -> ChatCallResult:
    # Unified chat endpoint with optional JSON-strict mode and tools/functions support.
    fmt = {"type": "json_object"} if json_strict else None
    return get_client().chat(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
        response_format=fmt, tools=tools, tool_choice=tool_choice,
        functions=functions, function_call=function_call, seed=seed, extra=extra,
    )

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

    prompt = (
        "Analyze the following company website text and extract: the official "
        "company name, the primary location or headquarters, the company's "
        "mission or mission statement, core values or culture. Respond in JSON "
        "with keys name, location, mission, culture.\n\n"
        f"{text}"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        answer = call_chat_api(
            messages,
            model=model,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        data = json.loads(answer)
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
    half = num_suggestions // 2
    prompt = (
        f"Suggest {half} technical and {half} soft skills for a {job_title} role. "
        "Avoid duplicates or skills already listed. Provide each skill on a separate line, prefixed by '-' or '•'."
    )
    if responsibilities:
        prompt += f" Key responsibilities: {responsibilities}. "
    if existing_skills:
        prompt += f" Already listed: {', '.join(existing_skills)}."
    # If language is German, ask in German to get German skill names
    if lang.startswith("de"):
        prompt = (
            f"Gib {half} technische und {half} soziale Fähigkeiten für die Position '{job_title}' an. "
            "Vermeide Dubletten oder bereits aufgeführte Fähigkeiten. Nenne jede Fähigkeit in einer neuen Zeile, beginnend mit '-' oder '•'."
        )
        if responsibilities:
            prompt += f" Wichtige Aufgaben: {responsibilities}. "
        if existing_skills:
            prompt += f" Bereits aufgelistet: {', '.join(existing_skills)}."
    messages = [{"role": "user", "content": prompt}]
    max_tokens = 220 if not model or "gpt-3.5" in model else 300
    answer = call_chat_api(
        messages, model=model, temperature=0.4, max_tokens=max_tokens
    )
    tech_skills, soft_skills = [], []
    bucket = "tech"
    for line in answer.splitlines():
        skill = line.strip("-•* \t")
        if not skill:
            continue
        # Switch bucket if the answer explicitly labels sections
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


def suggest_benefits(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    model: str | None = None,
) -> list[str]:
    """Suggest common benefits/perks for the given role.

    Args:
        job_title: Target role title.
        industry: Optional industry context.
        existing_benefits: Benefits already provided by the user.
        model: Optional OpenAI model override.

    Returns:
        A list of new benefit suggestions.
    """
    job_title = job_title.strip()
    if not job_title:
        return []
    prompt = f"List 5 benefits or perks commonly offered for a {job_title} role"
    if industry:
        prompt += f" in the {industry} industry"
    prompt += ". Avoid mentioning any benefit that's already listed below.\n"
    if existing_benefits:
        prompt += f"Already listed: {existing_benefits}"
    # If the interface language is German, request output in German
    # (We infer language from existing_benefits text as a simple heuristic or use a global if set)
    try:
        ui_lang = (
            "de"
            if "lang" in existing_benefits.lower() or "Vorteil" in existing_benefits
            else "en"
        )
    except Exception:
        ui_lang = "en"
    if ui_lang == "de":
        prompt = f"Nenne 5 Vorteile oder Zusatzleistungen, die für eine Stelle als {job_title} üblich sind"
        if industry:
            prompt += f" in der Branche {industry}"
        prompt += ". Vermeide Vorteile, die bereits in der Liste unten stehen.\n"
        if existing_benefits:
            prompt += f"Bereits aufgelistet: {existing_benefits}"
    messages = [{"role": "user", "content": prompt}]
    max_tokens = 150 if not model or "gpt-3.5" in model else 200
    answer = call_chat_api(
        messages, model=model, temperature=0.5, max_tokens=max_tokens
    )
    benefits = []
    for line in answer.splitlines():
        perk = line.strip("-•* \t")
        if perk:
            benefits.append(perk)
    # Filter out any benefits that were already present (case-insensitive match)
    existing_set = {b.strip().lower() for b in existing_benefits.splitlines()}
    benefits = [b for b in benefits if b.strip().lower() not in existing_set]
    return benefits


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
    prompt = f"List {num_tasks} concise core responsibilities for a {job_title} role."
    messages = [{"role": "user", "content": prompt}]
    max_tokens = 180 if not model or "gpt-3.5" in model else 250
    answer = call_chat_api(
        messages, model=model, temperature=0.5, max_tokens=max_tokens
    )
    tasks = []
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
    return call_chat_api(messages, model=model, temperature=0.7, max_tokens=1000)


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
        ("requirements.hard_skills", "Hard Skills", "Technische Fähigkeiten"),
        ("requirements.soft_skills", "Soft Skills", "Soziale Fähigkeiten"),
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
        ("position.application_deadline", "Application Deadline", "Bewerbungsschluss"),
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
    details: List[str] = []
    yes_no = ("Ja", "Nein") if lang.startswith("de") else ("Yes", "No")
    boolean_fields = {
        "employment.travel_required",
        "employment.relocation_support",
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
            if detail:
                formatted = f"{formatted} ({detail})"
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
    return call_chat_api(messages, model=model, temperature=0.7, max_tokens=600)


def refine_document(original: str, feedback: str, model: str | None = None) -> str:
    """Adjust a generated document using user feedback.

    Args:
        original: The original generated document.
        feedback: Instructions from the user describing desired changes.
        model: Optional OpenAI model override.

    Returns:
        The revised document text.
    """
    prompt = (
        "Revise the following document based on the user instructions.\n"
        f"Document:\n{original}\n\n"
        f"Instructions: {feedback}"
    )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, model=model, temperature=0.7, max_tokens=800)


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
    keys_used = [k for k, v in session_data.items() if v]
    prompt = (
        f"Explain how the following {doc_type} was generated using the keys: {', '.join(keys_used)}.\n"
        f"{doc_type.title()}:\n{output}"
    )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, model=model, temperature=0.3, max_tokens=300)
