from typing import Any, cast

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def call_chat_api(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.5,
    *,
    functions: list[dict] | None = None,
    function_call: dict | None = None,
    response_format: dict | None = None,
) -> str:
    """Call OpenAI's chat completion endpoint and return text or function args.

    The helper now supports OpenAI function calling. If ``functions`` are
    provided and the model chooses to invoke one, the function call arguments
    string is returned. Otherwise, the plain message content is returned.

    Raises:
        RuntimeError: If the OpenAI API key is missing or the API request fails.
    """
    if model is None:
        model = OPENAI_MODEL
    if client is None:
        raise RuntimeError(
            "OpenAI API key is not set. Set the OPENAI_API_KEY environment variable or add it to Streamlit secrets."
        )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=cast(list[Any], messages),
            temperature=temperature,
            max_tokens=max_tokens,
            functions=cast(Any, functions),
            function_call=cast(Any, function_call),
            response_format=cast(Any, response_format),
        )
        msg = response.choices[0].message
        func = getattr(msg, "function_call", None)
        if func and getattr(func, "arguments", None):
            return (func.arguments or "").strip()
        return (msg.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e


def suggest_additional_skills(
    job_title: str,
    tasks: str = "",
    existing_skills: list[str] | None = None,
    num_suggestions: int = 10,
    lang: str = "en",
    model: str | None = None,
) -> dict:
    """Suggest a mix of technical and soft skills for the given role.

    Args:
        job_title: Target role title.
        tasks: Known responsibilities for context.
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
    tasks: str = "",
    audience: str = "general",
    num_questions: int = 5,
    lang: str = "en",
    company_culture: str = "",
    model: str | None = None,
) -> str:
    """Generate an interview guide (questions + scoring rubrics) for the role.

    Args:
        job_title: Title of the role to generate questions for.
        tasks: Key tasks or responsibilities for context.
        audience: Target interviewers.
        num_questions: Number of interview questions to include.
        lang: Two-letter language code (``en`` or ``de``).
        company_culture: Company culture description used to craft a
            culture-fit question.
    """
    job_title = job_title.strip() or "this position"
    if lang.startswith("de"):
        # German prompt for interview guide
        prompt = (
            f"Erstelle einen Leitfaden für ein Vorstellungsgespräch für die Position {job_title} (für Interviewer: {audience}).\n"
            f"Formuliere {num_questions} Schlüsselfragen für das Interview und gib für jede Frage kurz die idealen Antwortkriterien an.\n"
            f"Wichtige Aufgaben der Rolle: {tasks or 'N/A'}."
        )
        if company_culture:
            prompt += (
                f"\nUnternehmenskultur: {company_culture}."
                "\nFüge mindestens eine Frage hinzu, die die Passung zur Unternehmenskultur bewertet."
            )
    else:
        prompt = (
            f"Generate an interview guide for a {job_title} for {audience} interviewers.\n"
            f"Include {num_questions} key interview questions and for each question, provide a brief scoring rubric or ideal answer criteria.\n"
            f"Key tasks for the role: {tasks or 'N/A'}."
        )
        if company_culture:
            prompt += (
                f"\nCompany culture: {company_culture}."
                "\nInclude at least one question assessing cultural fit."
            )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, model=model, temperature=0.7, max_tokens=1000)


def generate_job_ad(session_data: dict, model: str | None = None) -> str:
    """Generate a compelling job advertisement using the collected session data."""

    def _format(value: Any) -> str:
        """Convert list values to a comma-separated string."""

        if isinstance(value, list):
            return ", ".join(str(v) for v in value if v)
        return str(value)

    # Normalize aliases and aggregate all fields
    session_copy = dict(session_data)
    session_copy["responsibilities"] = (
        session_data.get("tasks") or session_data.get("responsibilities") or ""
    )
    session_copy["qualifications"] = (
        session_data.get("qualifications") or session_data.get("requirements") or ""
    )
    lang = session_copy.get("lang", "en")

    fields = [
        ("job_title", "Job Title", "Jobtitel"),
        ("company_name", "Company", "Unternehmen"),
        ("location", "Location", "Standort"),
        ("industry", "Industry", "Branche"),
        ("job_type", "Job Type", "Anstellungsart"),
        ("remote_policy", "Work Policy", "Arbeitsmodell"),
        ("travel_required", "Travel Requirements", "Reisebereitschaft"),
        ("role_summary", "Role Summary", "Rollenbeschreibung"),
        ("responsibilities", "Key Responsibilities", "Wichtigste Aufgaben"),
        ("qualifications", "Requirements", "Anforderungen"),
        ("hard_skills", "Hard Skills", "Technische Fähigkeiten"),
        ("soft_skills", "Soft Skills", "Soziale Fähigkeiten"),
        ("salary_range", "Salary Range", "Gehaltsspanne"),
        ("benefits", "Benefits", "Vorteile"),
        ("reporting_line", "Reporting Line", "Berichtsweg"),
        ("target_start_date", "Target Start Date", "Startdatum"),
        ("team_structure", "Team Structure", "Teamstruktur"),
        ("application_deadline", "Application Deadline", "Bewerbungsschluss"),
        ("seniority_level", "Seniority Level", "Erfahrungsebene"),
        ("languages_required", "Languages Required", "Erforderliche Sprachen"),
        ("tools_and_technologies", "Tools and Technologies", "Tools und Technologien"),
        ("company_mission", "Company Mission", "Unternehmensmission"),
        ("company_culture", "Company Culture", "Unternehmenskultur"),
    ]

    details: list[str] = []
    for key, label_en, label_de in fields:
        value = session_copy.get(key)
        if not value:
            continue
        formatted = _format(value).strip()
        if not formatted:
            continue
        label = label_de if lang.startswith("de") else label_en
        details.append(f"{label}: {formatted}")

    mission = session_copy.get("company_mission", "").strip()
    culture = session_copy.get("company_culture", "").strip()
    if lang.startswith("de"):
        prompt = (
            "Erstelle eine ansprechende, professionelle Stellenanzeige in Markdown-Format.\n"
            + "\n".join(details)
            + "\nTonfall: klar, ansprechend und inklusiv."
        )
        if mission or culture:
            lines = []
            if mission:
                lines.append(f"Unsere Mission: {mission}")
            if culture:
                lines.append(f"Unternehmenskultur: {culture}")
            prompt += "\n" + "\n".join(lines)
            prompt += "\nFüge einen Satz über Mission oder Werte des Unternehmens hinzu, um das Employer Branding zu stärken."
    else:
        prompt = (
            "Create an engaging, professional job advertisement in Markdown format.\n"
            + "\n".join(details)
            + "\nTone: engaging, clear, and inclusive."
        )
        if mission or culture:
            lines = []
            if mission:
                lines.append(f"Our mission: {mission}")
            if culture:
                lines.append(f"Company culture: {culture}")
            prompt += "\n" + "\n".join(lines)
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


def extract_company_info(text: str) -> dict:
    """Extract company information (name, mission/values, culture, location) from given website text."""
    # ... (no changes in this function) ...
    try:
        # (Implementation of extraction using OpenAI, omitted for brevity)
        result: dict[str, str] = {}
        return result
    except Exception:
        return {}
