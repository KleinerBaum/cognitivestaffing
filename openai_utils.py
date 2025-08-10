from config import OPENAI_MODEL, OPENAI_API_KEY
import openai

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY


def call_chat_api(messages: list[dict], model: str = None, max_tokens: int = 500, temperature: float = 0.5) -> str:
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
    if existing_skills is None:
        existing_skills = []
    job_title = job_title.strip()
    if not job_title:
        return {"technical": [], "soft": []}
    half = num_suggestions // 2
    prompt = (
        f"Suggest {half} technical and {half} soft skills for a {job_title} role. "
        "Avoid duplicates. Keep items concise."
    )
    if tasks:
        prompt += f" Key tasks: {tasks}. "
    if existing_skills:
        prompt += f" Already listed: {', '.join(existing_skills)}."
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.4, max_tokens=220)
    tech_skills, soft_skills, bucket = [], [], "tech"
    for line in answer.splitlines():
        t = line.strip("-•* \t").strip()
        if not t:
            continue
        # simple split heuristic
        if t.lower().startswith("soft"):
            bucket = "soft"
            continue
        if t.lower().startswith("technical"):
            bucket = "tech"
            continue
        (soft_skills if bucket == "soft" else tech_skills).append(t)
    existing_lower = {s.lower() for s in existing_skills}
    tech_skills = [s for s in tech_skills if s.lower() not in existing_lower]
    soft_skills = [s for s in soft_skills if s.lower() not in existing_lower]
    try:
        from esco_utils import enrich_skills_with_esco
        tech_skills = enrich_skills_with_esco(tech_skills, lang=lang)
        soft_skills = enrich_skills_with_esco(soft_skills, lang=lang)
    except Exception:
        pass
    return {"technical": tech_skills, "soft": soft_skills}


def suggest_role_tasks(job_title: str, num_tasks: int = 5) -> list[str]:
    job_title = job_title.strip()
    if not job_title:
        return []
    prompt = f"List {num_tasks} concise responsibilities for a {job_title} role."
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.5, max_tokens=180)
    tasks = []
    for line in answer.splitlines():
        t = line.strip("-•* \t")
        if t:
            tasks.append(t)
    return tasks[:num_tasks]


def generate_interview_guide(job_title: str, tasks: str = "", audience: str = "general", num_questions: int = 5) -> str:
    prompt = (
        f"Generate an interview guide for a {job_title} role for {audience} interviewers.\n"
        f"Include {num_questions} key questions. Key tasks: {tasks or 'N/A'}.\n"
        "For each question, include a brief scoring rubric."
    )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, temperature=0.7, max_tokens=1000)


def generate_job_ad(session_data: dict) -> str:
    job_title = session_data.get("job_title", "")
    company = session_data.get("company_name", "")
    location = session_data.get("location", "")
    tasks = session_data.get("tasks", "") or session_data.get("responsibilities", "")
    benefits = session_data.get("benefits", "")
    role_desc = session_data.get("role_summary", "")
    prompt = (
        "Create a compelling job advertisement.\n"
        f"Job Title: {job_title}\nCompany: {company}\nLocation: {location}\n"
        f"Role Summary: {role_desc}\nKey Responsibilities: {tasks}\nBenefits: {benefits}\n"
        "Tone: engaging, professional, concise. Output Markdown."
    )
    messages = [{"role": "user", "content": prompt}]
    return call_chat_api(messages, temperature=0.7, max_tokens=600)
