import streamlit as st
from utils import extract_text_from_file, highlight_keywords, build_boolean_query, seo_optimize
from openai_utils import suggest_additional_skills, suggest_role_tasks, generate_interview_guide, generate_job_ad
from esco_utils import lookup_esco_skill

# 1. Global Styling with Tailwind-like design
def apply_global_styling():
    """Inject custom CSS to give a modern look (using Tailwind-like styles)."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@300;400;700&display=swap');
    /* Base background and text */
    body, .stApp {
        background-color: #353536;
        color: #b1b3b3;
        font-family: 'Comfortaa', sans-serif;
    }
    /* Headers */
    h1, h2, h3, h4 {
        color: #ffffff;
    }
    /* Progress bar fill */
    .stProgress > div > div {
        background-color: #2e3232;
    }
    /* Buttons */
    .stButton > button {
        background-color: #2e3232;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-size: 1rem;
        cursor: pointer;
    }
    .stButton > button:hover {
        background-color: #454949;
        transition: all 0.2s ease;
    }
    /* File uploader label */
    .stFileUploader label {
        color: #b1b3b3;
    }
    /* Container "card" style */
    .card {
        background-color: #2e3232;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .streamlit-expanderHeader {
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Progress bar and navigation controls
def show_progress_bar(current_step: int, total_steps: int):
    progress = (current_step + 1) / total_steps
    percent = int(progress * 100)
    st.progress(progress, text=f"{percent}% complete")

def show_navigation(current_step: int, total_steps: int):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if current_step > 0:
            if st.button("⬅ Previous"):
                st.session_state["current_section"] -= 1
                st.experimental_rerun()
    with col3:
        if current_step < total_steps - 1:
            if st.button("Next ➡"):
                st.session_state["current_section"] += 1
                st.experimental_rerun()

# 3. Page step functions
def start_discovery_page():
    lang = st.session_state.get("lang", "en")
    # Title/intro
    if lang == "de":
        st.header("🔍 Spitzenkräfte finden: Vacalyser")
        st.write("Geben Sie einen Jobtitel ein oder laden Sie eine Stellenanzeige hoch. Die KI extrahiert alle wichtigen Informationen.")
    else:
        st.header("🔍 Start Your Analysis with Vacalyser")
        st.write("Enter a job title or upload a job posting. The AI will extract all key details for you.")
    # Inputs: job title, URL, file upload
    colA, colB = st.columns(2)
    with colA:
        job_title = st.text_input("Job Title", st.session_state.get("job_title", ""))
        if job_title:
            st.session_state["job_title"] = job_title
        input_url = st.text_input("Job Ad URL (optional)", st.session_state.get("input_url", ""))
        if input_url:
            st.session_state["input_url"] = input_url
    with colB:
        uploaded_file = st.file_uploader("Upload Job Ad (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            text = extract_text_from_file(file_bytes, uploaded_file.name)
            if text:
                st.session_state["uploaded_text"] = text
                st.success("✅ File uploaded and text extracted.")
            else:
                st.error("❌ Failed to extract text from the file.")
    # Analyze button
    if st.button("🔎 Analyze"):
        combined_text = ""
        # If both URL and file given, prioritize URL (or combine)
        if st.session_state.get("input_url"):
            # Try extracting from URL (job ad or company page)
            try:
                from readability import Document
                import requests
                resp = requests.get(st.session_state["input_url"], timeout=8)
                if resp.status_code == 200:
                    doc = Document(resp.text)
                    combined_text += doc.summary()
            except Exception as e:
                st.warning("Unable to fetch or parse URL content.")
        if st.session_state.get("uploaded_text"):
            combined_text += "\n" + st.session_state["uploaded_text"]
        if st.session_state.get("job_title") and not combined_text:
            # If no text from URL or file, at least use job title in prompt
            combined_text = st.session_state["job_title"]
        if not combined_text.strip():
            st.warning("⚠️ No text available to analyze.")
            return
        # Prepare extraction prompt for the LLM
        fields = ["company_name", "location", "company_website", "industry",
                  "role_summary", "tasks", "requirements", "salary_range",
                  "benefits", "health_benefits", "learning_opportunities", "remote_policy", "travel_required"]
        field_list_str = "".join([f"- {f}\n" for f in fields])
        extract_prompt = (
            f"You are a job advert parser. Extract the following information from the text below and return ONLY a JSON object with keys:\n"
            f"{field_list_str}\n"
            "If a field is not mentioned, use an empty string or empty list. Text:\n"
            f"{combined_text}"
        )
        # Call LLM (OpenAI or local model) to extract JSON
        from openai_utils import call_chat_api
        messages = [{"role": "user", "content": extract_prompt}]
        response = call_chat_api(messages, model=st.session_state.get("llm_model"))
        # Try to parse JSON
        import json
        try:
            parsed = json.loads(response)
            # Store each field in session state
            for key, value in parsed.items():
                # Normalize types: ensure strings for text fields
                if isinstance(value, list):
                    # join list to a multiline string for text areas
                    parsed_value = "\n".join(str(v) for v in value)
                else:
                    parsed_value = str(value)
                st.session_state[key] = parsed_value
            st.success("✅ Key information extracted successfully!")
        except json.JSONDecodeError:
            st.error("❌ Failed to parse AI response as JSON. Some fields may be missing.")
        # Log usage
        if "user" in st.session_state:
            log_event(f"ANALYZE performed by {st.session_state['user']} for job '{st.session_state.get('job_title','')}'")

def company_information_page():
    lang = st.session_state.get("lang", "en")
    st.header("🏢 Company Information" if lang != "de" else "🏢 Firmeninformationen")
    # Basic company fields
    company_name = st.text_input("Company Name" if lang != "de" else "Unternehmensname",
                                 st.session_state.get("company_name", ""))
    st.session_state["company_name"] = company_name
    industry = st.text_input("Industry" if lang != "de" else "Branche",
                              st.session_state.get("industry", ""))
    st.session_state["industry"] = industry
    location = st.text_input("Location" if lang != "de" else "Standort",
                              st.session_state.get("location", ""))
    st.session_state["location"] = location
    company_site = st.text_input("Company Website" if lang != "de" else "Webseite",
                                 st.session_state.get("company_website", ""))
    st.session_state["company_website"] = company_site

def role_description_page():
    lang = st.session_state.get("lang", "en")
    st.header("📋 Role Description" if lang != "de" else "📋 Stellenbeschreibung")
    # Role summary/introductory paragraph
    role_summary = st.text_area("Role Summary" if lang != "de" else "Rollenbeschreibung",
                                st.session_state.get("role_summary", ""),
                                height=100)
    st.session_state["role_summary"] = role_summary
    # Optionally job requirements/summary from extraction (could be stored in "requirements")
    requirements = st.text_area("Requirements/Qualifications" if lang != "de" else "Anforderungen/Qualifikationen",
                                st.session_state.get("requirements", ""), height=100)
    st.session_state["requirements"] = requirements

def task_scope_page():
    lang = st.session_state.get("lang", "en")
    st.header("📝 Key Tasks & Responsibilities" if lang != "de" else "📝 Wichtige Aufgaben & Verantwortlichkeiten")
    tasks_text = st.text_area("Tasks (one per line)" if lang != "de" else "Aufgaben (eine pro Zeile)",
                               st.session_state.get("tasks", ""), height=150)
    st.session_state["tasks"] = tasks_text
    if st.button("💡 Suggest Tasks"):
        job_title = st.session_state.get("job_title", "")
        suggestions = suggest_role_tasks(job_title, num_tasks=5)
        if suggestions:
            # Append suggestions to the tasks field, avoiding duplicates
            current_tasks = tasks_text.splitlines() if tasks_text else []
            for task in suggestions:
                if task and task not in current_tasks:
                    current_tasks.append(task)
            new_tasks_str = "\n".join(current_tasks)
            st.session_state["tasks"] = new_tasks_str
            st.success("✔️ Added suggested tasks.")
        else:
            st.warning("No suggestions available.")
        # Immediately update the text area with new tasks
        st.experimental_rerun()

def skills_competencies_page():
    lang = st.session_state.get("lang", "en")
    st.header("🛠️ Required Skills & Competencies" if lang != "de" else "🛠️ Erforderliche Fähigkeiten & Kompetenzen")
    hard_skills = st.text_area("Hard/Technical Skills" if lang != "de" else "Fachliche (Hard) Skills",
                               st.session_state.get("hard_skills", st.session_state.get("requirements", "")),
                               height=100)
    st.session_state["hard_skills"] = hard_skills
    soft_skills = st.text_area("Soft Skills" if lang != "de" else "Soft Skills",
                               st.session_state.get("soft_skills", ""), height=100)
    st.session_state["soft_skills"] = soft_skills
    # Suggest additional skills button
    if st.button("💡 Suggest Additional Skills"):
        title = st.session_state.get("job_title", "")
        tasks = st.session_state.get("tasks", "")
        existing = []
        # Combine already listed hard + soft skills into one list
        if hard_skills:
            existing += [s.strip() for s in hard_skills.splitlines() if s.strip()]
        if soft_skills:
            existing += [s.strip() for s in soft_skills.splitlines() if s.strip()]
        suggestions = suggest_additional_skills(title, tasks, existing, num_suggestions=10, lang=("de" if lang=="de" else "en"))
        tech_list = suggestions.get("technical", [])
        soft_list = suggestions.get("soft", [])
        # Merge suggestions with existing
        updated_hard = existing + [s for s in tech_list if s and s not in existing]
        updated_soft = [s for s in soft_list if s and s not in existing]
        st.session_state["hard_skills"] = "\n".join(updated_hard)
        st.session_state["soft_skills"] = "\n".join(updated_soft)
        st.success("✔️ Added skill suggestions.")
        st.experimental_rerun()

def benefits_compensation_page():
    lang = st.session_state.get("lang", "en")
    st.header("💰 Benefits & Compensation" if lang != "de" else "💰 Vergütung & Vorteile")
    salary = st.text_input("Salary Range", st.session_state.get("salary_range", ""))
    st.session_state["salary_range"] = salary
    benefits = st.text_area("Benefits/Perks", st.session_state.get("benefits", ""), height=100)
    st.session_state["benefits"] = benefits
    health = st.text_area("Healthcare Benefits", st.session_state.get("health_benefits", ""), height=70)
    st.session_state["health_benefits"] = health
    learning = st.text_area("Learning & Development Opportunities",
                             st.session_state.get("learning_opportunities", ""), height=70)
    st.session_state["learning_opportunities"] = learning
    remote = st.text_input("Remote Work Policy", st.session_state.get("remote_policy", ""))
    st.session_state["remote_policy"] = remote
    travel = st.text_input("Travel Requirements", st.session_state.get("travel_required", ""))
    st.session_state["travel_required"] = travel

def recruitment_process_page():
    lang = st.session_state.get("lang", "en")
    st.header("🏁 Recruitment Process" if lang != "de" else "🏁 Einstellungsprozess")
    rounds = st.number_input("Number of Interview Rounds" if lang != "de" else "Anzahl der Interviewrunden",
                              min_value=0, step=1, value=int(st.session_state.get("interview_stages", 0)))
    st.session_state["interview_stages"] = int(rounds)
    notes = st.text_area("Additional Hiring Process Notes" if lang != "de" else "Weitere Hinweise zum Prozess",
                          st.session_state.get("process_notes", ""), height=80)
    st.session_state["process_notes"] = notes

def summary_outputs_page():
    lang = st.session_state.get("lang", "en")
    st.header("📊 Summary & Outputs" if lang != "de" else "📊 Zusammenfassung & Ergebnisse")
    # Display key filled information
    st.write(f"**Job Title:** {st.session_state.get('job_title', '')}")
    st.write(f"**Company:** {st.session_state.get('company_name', '')}")
    st.write(f"**Location:** {st.session_state.get('location', '')}")
    st.write(f"**Industry:** {st.session_state.get('industry', '')}")
    st.write(f"**Role Summary:** {st.session_state.get('role_summary', '')}")
    st.write(f"**Key Tasks:** {st.session_state.get('tasks', '').replace('\\n', '; ')}")
    st.write(f"**Hard Skills:** {st.session_state.get('hard_skills', '').replace('\\n', '; ')}")
    st.write(f"**Soft Skills:** {st.session_state.get('soft_skills', '').replace('\\n', '; ')}")
    st.write(f"**Benefits:** {st.session_state.get('benefits', '').replace('\\n', '; ')}")
    st.write(f"**Salary Range:** {st.session_state.get('salary_range', '')}")
    # Buttons to generate outputs
    colA, colB = st.columns(2)
    with colA:
        if st.button("🎯 Generate Final Job Ad"):
            job_ad_text = generate_job_ad(st.session_state)
            st.subheader("Generated Job Advertisement")
            st.write(job_ad_text)
            # SEO suggestions for the generated ad
            seo = seo_optimize(job_ad_text)
            if seo["keywords"]:
                st.markdown(f"**SEO Keywords:** `{', '.join(seo['keywords'])}`")
            if seo["meta_description"]:
                st.markdown(f"**Meta Description:** {seo['meta_description']}")
            # Log usage
            if "user" in st.session_state:
                log_event(f"JOB_AD generated by {st.session_state['user']}")
    with colB:
        if st.button("📝 Generate Interview Guide"):
            title = st.session_state.get("job_title", "")
            tasks = st.session_state.get("tasks", "")
            guide = generate_interview_guide(title, tasks, audience="hiring managers", num_questions=5)
            st.subheader("Interview Guide & Scoring Rubrics")
            st.write(guide)
            # Log usage
            if "user" in st.session_state:
                log_event(f"INTERVIEW_GUIDE generated by {st.session_state['user']}")
    # Also provide a Boolean search string for candidate sourcing
    if st.session_state.get("job_title") or st.session_state.get("hard_skills"):
        bool_query = build_boolean_query(st.session_state.get("job_title", ""), 
                                         (st.session_state.get("hard_skills","") + "\n" + st.session_state.get("soft_skills","")).splitlines())
        if bool_query:
            st.info(f"**Boolean Search Query:** `{bool_query}`")

# 4. Usage tracking (logging)
def log_event(event_text: str):
    # Log usage events to a file (or database if configured)
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {event_text}\n"
    try:
        # If a database were configured, we could insert into a usage table here.
        # For simplicity, append to a local log file.
        with open("logs/usage.log", "a") as f:
            f.write(entry)
    except Exception as e:
        # If file logging fails (e.g., no permission on Streamlit Cloud), just print
        print(entry)
