import os
import streamlit as st
from config import OPENAI_MODEL, OPENAI_API_KEY
import openai

# Ensure OpenAI API key is set
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Helper to call OpenAI ChatCompletion API
def call_chat_api(messages: list[dict], model: str = None, max_tokens: int = 500, temperature: float = 0.5) -> str:
    if model is None:
        model = OPENAI_MODEL
    try:
        response = openai.ChatCompletion.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        content = response["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        # Log the error and return empty string on failure
        print(f"OpenAI API call error: {e}")
        return ""

# Suggest additional skills (technical & soft) not already in the job ad
def suggest_additional_skills(job_title: str, tasks: str = "", existing_skills: list[str] = None, num_suggestions: int = 10, lang: str = "en") -> dict:
    if existing_skills is None:
        existing_skills = []
    job_title = job_title.strip()
    if not job_title:
        return {"technical": [], "soft": []}
    # Split the suggestions equally into technical vs soft skills
    half = num_suggestions // 2
    prompt = (
        f"You are an expert career advisor. Suggest {half} technical skills and {half} soft skills for a {job_title} role. "
        "Do not repeat skills already listed in the job description. "
    )
    if tasks:
        prompt += f"The role's key tasks are: {tasks}. "
    if existing_skills:
        prompt += f"Already listed skills: {', '.join(existing_skills)}. "
    prompt += "Respond with two sections labeled 'Technical Skills:' and 'Soft Skills:' each as a bullet list."
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.4, max_tokens=200)
    # Parse the answer into technical and soft lists
    tech_skills = []
    soft_skills = []
    for line in answer.splitlines():
        line = line.strip("-•* \t")
        if not line:
            continue
        if line.lower().startswith("technical skills"):
            # start of technical section
            continue
        if line.lower().startswith("soft skills"):
            # start of soft section
            continue
        # Determine which list we are in by simple heuristic
        if soft_skills or line.lower().startswith("soft"):
            # If we've seen the "Soft Skills" header or infer from content
            soft_skills.append(line)
        else:
            tech_skills.append(line)
    # Remove any skill already in existing_skills (case-insensitive)
    existing_lower = {s.lower(): s for s in existing_skills}
    tech_skills = [s for s in tech_skills if s.lower() not in existing_lower]
    soft_skills = [s for s in soft_skills if s.lower() not in existing_lower]
    # Optionally, standardize skills via ESCO
    try:
        from esco_utils import enrich_skills_with_esco
        tech_skills = enrich_skills_with_esco(tech_skills, lang=lang)
        soft_skills = enrich_skills_with_esco(soft_skills, lang=lang)
    except ImportError:
        pass
    return {"technical": tech_skills, "soft": soft_skills}

# Suggest key tasks/responsibilities for a role
def suggest_role_tasks(job_title: str, num_tasks: int = 5) -> list[str]:
    job_title = job_title.strip()
    if not job_title:
        return []
    prompt = (
        f"You are an experienced professional in the field. List {num_tasks} key responsibilities or tasks for a {job_title} position. "
        "Provide each as a concise bullet point."
    )
    messages = [{"role": "user", "content": prompt}]
    answer = call_chat_api(messages, temperature=0.5, max_tokens=150)
    tasks = []
    for line in answer.splitlines():
        line = line.strip("-•* \t")
        if line:
            tasks.append(line)
    return tasks[:num_tasks]

# Generate interview questions and (optionally) scoring guidelines for a given role
def generate_interview_guide(job_title: str, tasks: str = "", audience: str = "general", num_questions: int = 5) -> str:
    prompt = (
        f"You are an AI recruitment assistant. Generate an interview guide for a {job_title} role for {audience} interviewers.\n"
        f"Include {num_questions} key interview questions. The role's primary tasks are: {tasks or 'N/A'}.\n"
        "For each question, provide a brief note on what a strong answer should include (to serve as a scoring rubric)."
    )
    messages = [{"role": "user", "content": prompt}]
    guide_text = call_chat_api(messages, temperature=0.7, max_tokens=1000)
    return guide_text.strip()

# Generate a job advertisement text from structured data
def generate_job_ad(session_data: dict) -> str:
    job_title = session_data.get("job_title", "")
    company = session_data.get("company_name", "")
    location = session_data.get("location", "")
    tasks = session_data.get("tasks", "") or session_data.get("responsibilities", "")
    benefits = session_data.get("benefits", "")
    role_desc = session_data.get("role_summary", "")
    prompt = (
        "You are an AI HR copywriter. Create a compelling job advertisement for the following position.\n"
        f"Job Title: {job_title}\nCompany: {company}\nLocation: {location}\n"
        f"Role Summary: {role_desc}\nKey Responsibilities: {tasks}\nBenefits: {benefits}\n"
        "The tone should be engaging, professional, and concise. Output the job ad in clear paragraphs."
    )
    messages = [{"role": "user", "content": prompt}]
    job_ad_text = call_chat_api(messages, temperature=0.7, max_tokens=500)
    return job_ad_text.strip()
