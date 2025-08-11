import json
import streamlit as st
from core.ss_bridge import from_session_state, to_session_state
from core.schema import ALIASES
from utils import (
    extract_text_from_file,
    extract_text_from_url,
    merge_texts,
    build_boolean_query,
    seo_optimize,
    ensure_logs_dir,
)
from openai_utils import (
    call_chat_api,
    suggest_additional_skills,
    suggest_benefits,
    suggest_role_tasks,
    generate_interview_guide,
    generate_job_ad,
    extract_company_info,
)
from question_logic import generate_followup_questions, EXTENDED_FIELDS

def normalise_state(reapply_aliases: bool = True):
    """Normalize session state to canonical schema keys and update JSON."""
    jd = from_session_state(st.session_state)
    to_session_state(jd, st.session_state)
    if reapply_aliases:
        # Keep legacy alias fields in sync for UI (if needed)
        st.session_state["requirements"] = st.session_state.get("qualifications", "")
        st.session_state["tasks"] = st.session_state.get("responsibilities", "")
        st.session_state["contract_type"] = st.session_state.get("job_type", "")
    st.session_state["validated_json"] = json.dumps(
        jd.model_dump(mode="json"), indent=2, ensure_ascii=False
    )
    return jd

def apply_global_styling():
    """Apply global CSS styles to the Streamlit app."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@300;400;700&display=swap');
        body, .stApp { background-color: #0b0f14; color: #e5e7eb; font-family: 'Comfortaa', sans-serif; }
        h1,h2,h3,h4 { color: #ffffff; }
        .card { background-color: #111827; padding: 1rem; border-radius: 12px; margin-bottom: 1.25rem; }
        .stButton > button { border-radius: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def show_progress_bar(current_step: int, total_steps: int):
    progress = (current_step + 1) / total_steps
    st.progress(progress, text=f"{int(progress*100)}% complete")

def show_navigation(current_step: int, total_steps: int):
    """Render Previous/Next navigation buttons for the wizard."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if current_step > 0:
            if st.button("⬅ Previous"):
                st.session_state["current_section"] -= 1
                st.rerun()
    with col3:
        if current_step < total_steps - 1:
            if st.button("Next ➡"):
                st.session_state["current_section"] += 1
                st.rerun()

def start_discovery_page():
    """Start page: Input job title and job ad content (URL or file) for analysis."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🔍 Start Your Analysis with Vacalyzer"
        if lang != "de" else "🔍 Starten Sie Ihre Analyse mit Vacalyzer"
    )
    st.caption(
        "Upload a job ad or paste a URL. We’ll extract everything we can — then ask only what’s missing."
        if lang != "de" else "Laden Sie eine Stellenanzeige hoch oder fügen Sie eine URL ein. Wir extrahieren alle verfügbaren Informationen und fragen nur noch fehlende Details ab."
    )

    # Job title and source inputs
    colA, colB = st.columns(2)
    with colA:
        job_title = st.text_input(
            "Job Title" if lang != "de" else "Stellenbezeichnung",
            st.session_state.get("job_title", ""),
        )
        if job_title:
            st.session_state["job_title"] = job_title
        input_url = st.text_input(
            "Job Ad URL (optional)" if lang != "de" else "Stellenanzeigen-URL (optional)",
            st.session_state.get("input_url", ""),
        )
        if input_url:
            st.session_state["input_url"] = input_url
    with colB:
        uploaded_file = st.file_uploader(
            "Upload Job Ad (PDF, DOCX, TXT)" if lang != "de" else "Stellenanzeige hochladen (PDF, DOCX, TXT)",
            type=["pdf", "docx", "txt"],
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            text = extract_text_from_file(file_bytes, uploaded_file.name)
            if text:
                st.session_state["uploaded_text"] = text
                st.success("✅ File uploaded and text extracted.")
            else:
                st.error("❌ Failed to extract text from the file.")

    # Analyze button triggers extraction
    if st.button("🔎 Analyze"):
        url_text = ""
        if st.session_state.get("input_url"):
            url_text = extract_text_from_url(st.session_state["input_url"])
            if not url_text:
                st.warning("⚠️ Unable to fetch or parse content from the provided URL.")
        file_text = st.session_state.get("uploaded_text", "")
        combined_text = merge_texts(url_text, file_text)
        # If no text source but job title is provided, use job title as fallback text
        if st.session_state.get("job_title") and not combined_text:
            combined_text = st.session_state["job_title"]

        if not combined_text:
            st.warning("⚠️ No text available to analyze. Please provide a job ad URL or upload a document.")
            return

        # Construct prompt for extracting all extended fields from text
        field_list = "".join([f"- {f}\n" for f in EXTENDED_FIELDS])
        extract_prompt = (
            "Extract the following fields from the job advertisement text. "
            "Return ONLY a JSON object with these keys:\n"
            f"{field_list}\n"
            "Use an empty string or empty list for any field that is not present in the text.\n"
            f"Text:\n{combined_text}"
        )
        messages = [{"role": "user", "content": extract_prompt}]
        response = call_chat_api(messages, model=st.session_state.get("llm_model"), temperature=0.0)
        import json
        try:
            parsed = json.loads(response)
            # Update session state with extracted values
            for key, val in parsed.items():
                # Join lists into newline-separated strings for text areas
                st.session_state[key] = "\n".join(val) if isinstance(val, list) else str(val)
            normalise_state()  # normalize keys and prepare validated JSON
            # Generate follow-up questions for missing info
            followups = generate_followup_questions(st.session_state, lang=lang)
            st.session_state["followup_questions"] = followups
            st.success("✅ Key information extracted successfully!")
            log_event(
                f"ANALYZE by {st.session_state.get('user', 'anonymous')} title='{st.session_state.get('job_title', '')}'"
            )
        except json.JSONDecodeError:
            st.error("❌ Could not parse AI response as JSON. Please try again or rephrase the input.")

def followup_questions_page():
    """Follow-up page: Display dynamically generated follow-up questions for missing fields."""
    lang = st.session_state.get("lang", "en")
    st.header("❓ Additional Questions" if lang != "de" else "❓ Zusätzliche Fragen")
    followups = st.session_state.get("followup_questions", [])
    if not followups:
        st.info(
            "No further questions – vacancy profile looks complete."
            if lang != "de" else "Keine weiteren Fragen – das Profil ist vollständig."
        )
        return
    # Render each follow-up question as a text input
    for item in followups:
        field = item.get("field", "")
        question = item.get("question", "")
        # Use field as the Streamlit key if available, otherwise use the question text as key
        key = field or question
        if field:
            st.session_state[field] = st.text_input(question, st.session_state.get(field, ""), key=key)
        else:
            # Question with no specific field: provide an input for user response (not stored in schema)
            _ = st.text_input(question, "", key=key)

def company_information_page():
    """Company Info page: Gather basic company information and optionally auto-fetch details from website."""
    lang = st.session_state.get("lang", "en")
    st.header("🏢 Company Information" if lang != "de" else "🏢 Firmeninformationen")
    st.session_state["company_name"] = st.text_input(
        "Company Name" if lang != "de" else "Unternehmensname",
        st.session_state.get("company_name", ""),
    )
    st.session_state["industry"] = st.text_input(
        "Industry" if lang != "de" else "Branche",
        st.session_state.get("industry", ""),
    )
    st.session_state["location"] = st.text_input(
        "Location" if lang != "de" else "Standort",
        st.session_state.get("location", ""),
    )
    st.session_state["company_website"] = st.text_input(
        "Company Website" if lang != "de" else "Webseite",
        st.session_state.get("company_website", ""),
    )
    # Optional: Fetch company info (mission, values, etc.) from website
    if st.button("🔄 Fetch Company Info from Website"):
        website = st.session_state.get("company_website", "").strip()
        if not website:
            st.warning("Please enter a company website URL first.")
        else:
            # Ensure URL has protocol
            if not website.startswith("http"):
                website = "https://" + website
            # Try fetching main page text and impressum/about page text
            main_text = extract_text_from_url(website)
            impressum_text = ""
            if "/impressum" not in website.lower():
                # Attempt to fetch German "Impressum" page for company legal info
                impressum_url = website.rstrip("/") + "/impressum"
                impressum_text = extract_text_from_url(impressum_url)
            combined_site_text = merge_texts(main_text, impressum_text)
            if not combined_site_text:
                st.error("❌ Could not retrieve any text from the website.")
            else:
                # Use OpenAI to extract company details (name, mission, culture, location) from site text
                info = extract_company_info(combined_site_text)
                # Update session state with any info found (if fields were empty or not set by user yet)
                if info.get("company_name") and not st.session_state.get("company_name"):
                    st.session_state["company_name"] = info["company_name"]
                if info.get("location") and not st.session_state.get("location"):
                    st.session_state["location"] = info["location"]
                if info.get("company_mission"):
                    st.session_state["company_mission"] = info["company_mission"]
                if info.get("company_culture"):
                    st.session_state["company_culture"] = info["company_culture"]
                st.success("✅ Company information fetched from website.")
                # If mission or culture were fetched, add them to follow-up questions if they were missing
                # (So that user can see and edit them if needed in follow-ups)
                followups = st.session_state.get("followup_questions", [])
                if info.get("company_mission") and not any(f.get("field") == "company_mission" for f in followups):
                    followups.append({"field": "company_mission", "question": "Company Mission / Core Values"})
                if info.get("company_culture") and not any(f.get("field") == "company_culture" for f in followups):
                    followups.append({"field": "company_culture", "question": "Company Culture or Work Environment"})
                st.session_state["followup_questions"] = followups

def role_description_page():
    """Role Description page: High-level summary of the role and key requirements."""
    lang = st.session_state.get("lang", "en")
    st.header("📋 Role Description" if lang != "de" else "📋 Stellenbeschreibung")
    st.session_state["role_summary"] = st.text_area(
        "Role Summary" if lang != "de" else "Kurze Stellenbeschreibung",
        st.session_state.get("role_summary", ""),
        height=100,
    )
    # Combine requirements and qualifications in one field for user convenience
    req_initial = st.session_state.get("requirements") or st.session_state.get("qualifications", "")
    req_text = st.text_area(
        "Requirements/Qualifications" if lang != "de" else "Anforderungen/Qualifikationen",
        req_initial,
        height=100,
    )
    st.session_state["requirements"] = req_text
    st.session_state["qualifications"] = req_text

def task_scope_page():
    """Tasks page: Key tasks and responsibilities of the role, with suggestions."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "📝 Key Tasks & Responsibilities"
        if lang != "de" else "📝 Wichtige Aufgaben & Verantwortlichkeiten"
    )
    tasks_text = st.text_area(
        "Tasks (one per line)" if lang != "de" else "Aufgaben (eine pro Zeile)",
        st.session_state.get("tasks") or st.session_state.get("responsibilities", ""),
        height=150,
    )
    st.session_state["tasks"] = tasks_text
    st.session_state["responsibilities"] = tasks_text
    if st.button("💡 Suggest Tasks"):
        title = st.session_state.get("job_title", "")
        suggestions = suggest_role_tasks(title, num_tasks=5)
        if suggestions:
            current_tasks = [t.strip() for t in tasks_text.splitlines() if t.strip()]
            for t in suggestions:
                if t and t not in current_tasks:
                    current_tasks.append(t)
            st.session_state["tasks"] = "\n".join(current_tasks)
            st.session_state["responsibilities"] = st.session_state["tasks"]
            st.success("✔️ Added suggested tasks.")
            st.rerun()
        else:
            st.warning("No task suggestions available at the moment.")

def skills_competencies_page():
    """Skills page: Required hard and soft skills, with AI suggestions to enrich the list."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🛠️ Required Skills & Competencies"
        if lang != "de" else "🛠️ Erforderliche Fähigkeiten & Kompetenzen"
    )
    hard_skills_text = st.text_area(
        "Hard/Technical Skills" if lang != "de" else "Fachliche (Hard) Skills",
        st.session_state.get("hard_skills", st.session_state.get("requirements", "")),
        height=100,
    )
    st.session_state["hard_skills"] = hard_skills_text
    soft_skills_text = st.text_area(
        "Soft Skills" if lang != "de" else "Soft Skills",
        st.session_state.get("soft_skills", ""),
        height=100,
    )
    st.session_state["soft_skills"] = soft_skills_text
    if st.button("💡 Suggest Additional Skills"):
        title = st.session_state.get("job_title", "")
        tasks = st.session_state.get("tasks", "") or st.session_state.get("responsibilities", "")
        existing_skills = []
        if hard_skills_text:
            existing_skills += [s.strip() for s in hard_skills_text.splitlines() if s.strip()]
        if soft_skills_text:
            existing_skills += [s.strip() for s in soft_skills_text.splitlines() if s.strip()]
        suggestions = suggest_additional_skills(
            job_title=title,
            tasks=tasks,
            existing_skills=existing_skills,
            num_suggestions=10,
            lang="de" if lang == "de" else "en",
        )
        tech_suggestions = suggestions.get("technical", [])
        soft_suggestions = suggestions.get("soft", [])
        # Merge new suggestions avoiding duplicates
        updated_hard = existing_skills + [s for s in tech_suggestions if s and s.lower() not in [e.lower() for e in existing_skills]]
        updated_soft = [s for s in soft_suggestions if s and s.lower() not in [e.lower() for e in existing_skills]]
        st.session_state["hard_skills"] = "\n".join(updated_hard)
        st.session_state["soft_skills"] = "\n".join(updated_soft)
        st.success("✔️ Added skill suggestions.")
        st.rerun()

def benefits_compensation_page():
    """Benefits page: Compensation and benefits details, with suggestions for perks."""
    lang = st.session_state.get("lang", "en")
    st.header("💰 Benefits & Compensation" if lang != "de" else "💰 Vergütung & Vorteile")
    st.session_state["salary_range"] = st.text_input(
        "Salary Range", st.session_state.get("salary_range", "")
    )
    st.session_state["benefits"] = st.text_area(
        "Benefits/Perks", st.session_state.get("benefits", ""), height=100
    )
    st.session_state["health_benefits"] = st.text_area(
        "Healthcare Benefits", st.session_state.get("health_benefits", ""), height=70
    )
    st.session_state["learning_opportunities"] = st.text_area(
        "Learning & Development Opportunities",
        st.session_state.get("learning_opportunities", ""),
        height=70,
    )
    st.session_state["remote_policy"] = st.text_input(
        "Remote Work Policy", st.session_state.get("remote_policy", "")
    )
    st.session_state["travel_required"] = st.text_input(
        "Travel Requirements", st.session_state.get("travel_required", "")
    )
    if st.button("💡 Suggest Benefits"):
        title = st.session_state.get("job_title", "")
        industry = st.session_state.get("industry", "")
        existing = st.session_state.get("benefits", "")
        suggestions = suggest_benefits(title, industry, existing_benefits=existing)
        if suggestions:
            current_benefits = [b.strip() for b in st.session_state["benefits"].splitlines() if b.strip()]
            for perk in suggestions:
                if perk and perk not in current_benefits:
                    current_benefits.append(perk)
            st.session_state["benefits"] = "\n".join(current_benefits)
            st.success("✔️ Added suggested benefits/perks.")
            st.rerun()
        else:
            st.warning("No benefit suggestions available at the moment.")

def recruitment_process_page():
    """Process page: Details about the recruitment process (interview rounds, notes)."""
    lang = st.session_state.get("lang", "en")
    st.header("🏁 Recruitment Process" if lang != "de" else "🏁 Einstellungsprozess")
    st.session_state["interview_stages"] = int(
        st.number_input(
            "Number of Interview Rounds" if lang != "de" else "Anzahl der Interviewrunden",
            min_value=0,
            step=1,
            value=int(st.session_state.get("interview_stages", 0)),
        )
    )
    st.session_state["process_notes"] = st.text_area(
        "Additional Hiring Process Notes" if lang != "de" else "Weitere Hinweise zum Prozess",
        st.session_state.get("process_notes", ""),
        height=80,
    )

def summary_outputs_page():
    """Summary page: Display a summary of collected fields and provide output generation (job ad, interview guide, boolean query)."""
    lang = st.session_state.get("lang", "en")
    normalise_state(reapply_aliases=False)  # Final normalization (do not reapply alias values here)
    st.header("📊 Summary & Outputs" if lang != "de" else "📊 Zusammenfassung & Ergebnisse")
    # List of fields to display in summary (avoiding duplicate alias keys)
    fields_to_show = (
        ["job_title"]
        + [f for f in EXTENDED_FIELDS if f not in ALIASES]  # show all extended fields (aliases filtered out)
        + ["hard_skills", "soft_skills"]
    )
    seen_keys = set()
    for field in fields_to_show:
        if field in seen_keys:
            continue
        seen_keys.add(field)
        value = st.session_state.get(field)
        if value:
            # Format list values nicely, join with "; "
            display_val = str(value).replace("\n", "; ")
            st.write(f"**{field.replace('_', ' ').title()}:** {display_val}")
    # Buttons to generate final outputs
    colA, colB = st.columns(2)
    with colA:
        if st.button("🎯 Generate Final Job Ad"):
            job_ad_text = generate_job_ad(st.session_state)
            st.subheader("Generated Job Advertisement")
            st.write(job_ad_text)
            # Basic SEO optimization suggestions
            seo = seo_optimize(job_ad_text)
            if seo["keywords"]:
                st.markdown(f"**SEO Keywords:** `{', '.join(seo['keywords'])}`")
            if seo["meta_description"]:
                st.markdown(f"**Meta Description:** {seo['meta_description']}")
            log_event(f"JOB_AD by {st.session_state.get('user', 'anonymous')}")
    with colB:
        if st.button("📝 Generate Interview Guide"):
            title = st.session_state.get("job_title", "")
            tasks = st.session_state.get("tasks", "") or st.session_state.get("responsibilities", "")
            guide = generate_interview_guide(title, tasks, audience="hiring managers", num_questions=5)
            st.subheader("Interview Guide & Scoring Rubrics")
            st.write(guide)
            log_event(f"INTERVIEW_GUIDE by {st.session_state.get('user', 'anonymous')}")
    # Always display a suggested Boolean search query for recruiters
    if st.session_state.get("job_title") or st.session_state.get("hard_skills"):
        bool_query = build_boolean_query(
            st.session_state.get("job_title", ""),
            (st.session_state.get("hard_skills", "") + "\n" + st.session_state.get("soft_skills", "")).splitlines(),
        )
        if bool_query:
            st.info(f"**Boolean Search Query:** `{bool_query}`")

def log_event(event_text: str):
    """Append an event entry to the usage log with a timestamp."""
    ensure_logs_dir()
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {event_text}\n"
    try:
        with open("logs/usage.log", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        # If file write fails (e.g., no permission), print to console
        print(entry)
