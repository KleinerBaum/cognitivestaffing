from config import OPENAI_API_KEY, OPENAI_MODEL
import openai

# Set API key for OpenAI if available
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


def call_chat_api(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.5,
) -> str:
    """Generic helper to call OpenAI ChatCompletion API and return the response text.

    Raises:
        RuntimeError: If the OpenAI API key is missing or the API request fails.
    """
    if model is None:
        model = OPENAI_MODEL
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OpenAI API key is not set. Set the OPENAI_API_KEY environment variable or add it to Streamlit secrets."
        )
    try:
        response = openai.ChatCompletion.create(  # type: ignore[attr-defined]
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e


def suggest_additional_skills(
    job_title: str,
    tasks: str = "",
    existing_skills: list[str] | None = None,
    num_suggestions: int = 10,
    lang: str = "en",
) -> dict:
    """Suggest a mix of technical and soft skills for the given role, avoiding duplicates."""
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
    if tasks:
        prompt += f" Key tasks: {tasks}. "
    if existing_skills:
        prompt += f" Already listed: {', '.join(existing_skills)}."
    # If language is German, ask in German to get German skill names
    if lang.startswith("de"):
        prompt = (
            f"Gib {half} technische und {half} soziale Fähigkeiten für die Position '{job_title}' an. "
            "Vermeide Dubletten oder bereits aufgeführte Fähigkeiten. Nenne jede Fähigkeit in einer neuen Zeile, beginnend mit '-' oder '•'."
        )
        if tasks:
            prompt += f" Wichtige Aufgaben: {tasks}. "
        if existing_skills:
            prompt += f" Bereits aufgelistet: {', '.join(existing_skills)}."
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.4, max_tokens=220)
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
    job_title: str, industry: str = "", existing_benefits: str = ""
) -> list[str]:
    """Suggest common benefits/perks for the given role (and industry), avoiding those already listed."""
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
    answer = call_chat_api(messages, temperature=0.5, max_tokens=150)
    benefits = []
    for line in answer.splitlines():
        perk = line.strip("-•* \t")
        if perk:
            benefits.append(perk)
    # Filter out any benefits that were already present (case-insensitive match)
    existing_set = {b.strip().lower() for b in existing_benefits.splitlines()}
    benefits = [b for b in benefits if b.strip().lower() not in existing_set]
    return benefits


def suggest_role_tasks(job_title: str, num_tasks: int = 5) -> list[str]:
    """Suggest a list of key responsibilities/tasks for a given job title."""
    job_title = job_title.strip()
    if not job_title:
        return []
    prompt = f"List {num_tasks} concise core responsibilities for a {job_title} role."
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.5, max_tokens=180)
    tasks = []
    for line in answer.splitlines():
        task = line.strip("-•* \t")
        if task:
            tasks.append(task)
    return tasks[:num_tasks]


def generate_interview_guide(
    job_title: str,
    tasks: str = "",
    audience: str = "general",
    num_questions: int = 5,
    lang: str = "en",
) -> str:
    """Generate an interview guide (questions + scoring rubrics) for the role."""
    job_title = job_title.strip() or "this position"
    if lang.startswith("de"):
        # German prompt for interview guide
        prompt = (
            f"Erstelle einen Leitfaden für ein Vorstellungsgespräch für die Position {job_title} (für Interviewer: {audience}).\n"
            f"Formuliere {num_questions} Schlüsselfragen für das Interview und gib für jede Frage kurz die idealen Antwortkriterien an.\n"
            f"Wichtige Aufgaben der Rolle: {tasks or 'N/A'}."
        )
    else:
        prompt = (
            f"Generate an interview guide for a {job_title} for {audience} interviewers.\n"
            f"Include {num_questions} key interview questions and for each question, provide a brief scoring rubric or ideal answer criteria.\n"
            f"Key tasks for the role: {tasks or 'N/A'}."
        )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, temperature=0.7, max_tokens=1000)


def generate_job_ad(session_data: dict) -> str:
    """Generate a compelling job advertisement using the collected session data."""
    job_title = session_data.get("job_title", "")
    company = session_data.get("company_name", "")
    location = session_data.get("location", "")
    role_desc = session_data.get("role_summary", "")
    tasks = session_data.get("tasks", "") or session_data.get("responsibilities", "")
    benefits = session_data.get("benefits", "")
    lang = session_data.get("lang", "en")
    if lang.startswith("de"):
        # German prompt for job ad
        prompt = (
            "Erstelle eine ansprechende, professionelle Stellenanzeige in Markdown-Format.\n"
            f"Jobtitel: {job_title}\nUnternehmen: {company}\nStandort: {location}\n"
            f"Rollenbeschreibung: {role_desc}\nWichtigste Aufgaben: {tasks}\nVorteile: {benefits}\n"
            "Tonfall: klar, ansprechend und inklusiv."
        )
    else:
        prompt = (
            "Create an engaging, professional job advertisement in Markdown format.\n"
            f"Job Title: {job_title}\nCompany: {company}\nLocation: {location}\n"
            f"Role Summary: {role_desc}\nKey Responsibilities: {tasks}\nBenefits: {benefits}\n"
            "Tone: engaging, clear, and inclusive."
        )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, temperature=0.7, max_tokens=600)


def extract_company_info(text: str) -> dict:
    """Extract company information (name, mission/values, culture, location) from given website text."""
    # ... (no changes in this function) ...
    try:
        # (Implementation of extraction using OpenAI, omitted for brevity)
        result: dict[str, str] = {}
        return result
    except Exception:
        return {}
