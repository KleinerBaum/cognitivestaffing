from config import OPENAI_MODEL, OPENAI_API_KEY
import openai
import json

# Set API key for OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

def call_chat_api(messages: list[dict], model: str = None, max_tokens: int = 500, temperature: float = 0.5) -> str:
    """Generic helper to call OpenAI ChatCompletion API and return the response text."""
    if model is None:
        model = OPENAI_MODEL
    try:
        response = openai.ChatCompletion.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return (response["choices"][0]["message"]["content"] or "").strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return ""

def suggest_additional_skills(job_title: str, tasks: str = "", existing_skills: list[str] = None,
                              num_suggestions: int = 10, lang: str = "en") -> dict:
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
        if skill.lower().startswith("technical"):
            bucket = "tech"
            continue
        if bucket == "tech":
            tech_skills.append(skill)
        else:
            soft_skills.append(skill)
    # Remove any suggested skills that were already in existing_skills (case-insensitive)
    existing_lower = {s.lower() for s in existing_skills}
    tech_skills = [s for s in tech_skills if s.lower() not in existing_lower]
    soft_skills = [s for s in soft_skills if s.lower() not in existing_lower]
    # Optionally enrich skill names to ESCO preferred labels
    try:
        from esco_utils import enrich_skills_with_esco
        tech_skills = enrich_skills_with_esco(tech_skills, lang=lang)
        soft_skills = enrich_skills_with_esco(soft_skills, lang=lang)
    except Exception:
        pass
    return {"technical": tech_skills, "soft": soft_skills}

def suggest_benefits(job_title: str, industry: str = "", existing_benefits: str = "") -> list[str]:
    """Suggest common benefits/perks for the given role (and industry), avoiding those already listed."""
    job_title = job_title.strip()
    # If no specific role given, we cannot suggest targeted benefits
    if not job_title:
        return []
    prompt = f"List 5 benefits or perks commonly offered for a {job_title} role"
    if industry:
        prompt += f" in the {industry} industry"
    prompt += ". Avoid mentioning any benefit that's already listed below.\n"
    if existing_benefits:
        prompt += f"Already listed: {existing_benefits}"
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.5, max_tokens=150)
    benefits = []
    for line in answer.splitlines():
        perk = line.strip("-•* \t")
        if perk:
            benefits.append(perk)
    # Filter out any benefits that were already present
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

def generate_interview_guide(job_title: str, tasks: str = "", audience: str = "general", num_questions: int = 5) -> str:
    """Generate an interview guide (questions + scoring rubrics) for the role."""
    job_title = job_title.strip() or "this position"
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
    if not text or text.strip() == "":
        return {}
    # Limit length of text to avoid token overrun
    snippet = text[:3000]  # use first part if text is very long
    prompt = (
        "You are an assistant that extracts company information from website text. "
        "Identify the company name, the main location (city or country), any statement of the company's mission or core values, "
        "and any description of the company culture or work environment from the text below. "
        "Provide the answer as a JSON object with keys: company_name, location, company_mission, company_culture. "
        "If a field is not mentioned, use an empty string for it.\nText:\n"
        + snippet
    )
    messages = [{"role": "user", "content": prompt}]
    result = call_chat_api(messages, temperature=0.2, max_tokens=300)
    try:
        info = json.loads(result)
        # Ensure all expected keys are present in the returned dict
        for key in ["company_name", "location", "company_mission", "company_culture"]:
            info.setdefault(key, "")
        return info
    except json.JSONDecodeError:
        # If the response isn't valid JSON, return empty or minimal info
        return {}
