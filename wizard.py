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
    suggest_additional_skills,
    suggest_role_tasks,
    generate_interview_guide,
    generate_job_ad,
)
from question_logic import generate_followup_questions, EXTENDED_FIELDS


def normalise_state(reapply_aliases: bool = True):
    """Normalise session state to canonical schema keys."""

    jd = from_session_state(st.session_state)
    to_session_state(jd, st.session_state)
    if reapply_aliases:
        st.session_state["requirements"] = st.session_state.get("qualifications", "")
        st.session_state["tasks"] = st.session_state.get("responsibilities", "")
        st.session_state["contract_type"] = st.session_state.get("job_type", "")
    st.session_state["validated_json"] = jd.model_dump_json(
        indent=2, ensure_ascii=False
    )
    return jd


def apply_global_styling():
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
    lang = st.session_state.get("lang", "en")
    st.header(
        "🔍 Start Your Analysis with Vacalyser"
        if lang != "de"
        else "🔍 Starten Sie Ihre Analyse mit Vacalyser"
    )
    st.caption(
        "Upload a job ad or paste a URL. We’ll extract everything we can — then ask only what’s missing."
    )

    colA, colB = st.columns(2)
    with colA:
        job_title = st.text_input(
            "Job Title" if lang != "de" else "Stellenbezeichnung",
            st.session_state.get("job_title", ""),
        )
        if job_title:
            st.session_state["job_title"] = job_title
        input_url = st.text_input(
            (
                "Job Ad URL (optional)"
                if lang != "de"
                else "Stellenanzeigen-URL (optional)"
            ),
            st.session_state.get("input_url", ""),
        )
        if input_url:
            st.session_state["input_url"] = input_url
    with colB:
        uploaded_file = st.file_uploader(
            (
                "Upload Job Ad (PDF, DOCX, TXT)"
                if lang != "de"
                else "Stellenanzeige hochladen (PDF, DOCX, TXT)"
            ),
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

    if st.button("🔎 Analyze"):
        url_text = ""
        if st.session_state.get("input_url"):
            url_text = extract_text_from_url(st.session_state["input_url"])
            if not url_text:
                st.warning("Unable to fetch/parse URL content.")
        file_text = st.session_state.get("uploaded_text", "")
        combined_text = merge_texts(url_text, file_text)
        if st.session_state.get("job_title") and not combined_text:
            combined_text = st.session_state["job_title"]

        if not combined_text:
            st.warning("⚠️ No text available to analyze.")
            return

        field_list = "".join([f"- {f}\n" for f in EXTENDED_FIELDS])
        extract_prompt = (
            "Extract the following fields from the job ad text. Return ONLY a JSON object with these keys:\n"
            f"{field_list}\n"
            "Use empty string or empty list if a field is not present.\n"
            f"Text:\n{combined_text}"
        )
        from openai_utils import call_chat_api

        messages = [{"role": "user", "content": extract_prompt}]
        resp = call_chat_api(messages, model=st.session_state.get("llm_model"))
        import json

        try:
            parsed = json.loads(resp)
            for k, v in parsed.items():
                st.session_state[k] = "\n".join(v) if isinstance(v, list) else str(v)
            normalise_state()
            followups = generate_followup_questions(st.session_state, lang=lang)
            st.session_state["followup_questions"] = followups
            st.success("✅ Key information extracted successfully!")
            log_event(
                f"ANALYZE by {st.session_state.get('user', 'anonymous')} "
                f"title='{st.session_state.get('job_title', '')}'"
            )
        except json.JSONDecodeError:
            st.error("❌ Could not parse AI response as JSON.")


def followup_questions_page():
    """Display dynamically generated follow-up questions to the user."""
    lang = st.session_state.get("lang", "en")
    st.header("❓ Additional Questions" if lang != "de" else "❓ Zusätzliche Fragen")
    followups = st.session_state.get("followup_questions", [])
    if not followups:
        st.info(
            "No further questions – vacancy profile looks complete."
            if lang != "de"
            else "Keine weiteren Fragen – Profil vollständig."
        )
        return
    for item in followups:
        field = item.get("field", "")
        question = item.get("question", "")
        key = field or question
        if field:
            st.session_state[field] = st.text_input(
                question, st.session_state.get(field, ""), key=key
            )
        else:
            _ = st.text_input(question, "", key=key)


def company_information_page():
    lang = st.session_state.get("lang", "en")
    st.header("🏢 Company Information" if lang != "de" else "🏢 Firmeninformationen")
    st.session_state["company_name"] = st.text_input(
        "Company Name" if lang != "de" else "Unternehmensname",
        st.session_state.get("company_name", ""),
    )
    st.session_state["industry"] = st.text_input(
        "Industry" if lang != "de" else "Branche", st.session_state.get("industry", "")
    )
    st.session_state["location"] = st.text_input(
        "Location" if lang != "de" else "Standort", st.session_state.get("location", "")
    )
    st.session_state["company_website"] = st.text_input(
        "Company Website" if lang != "de" else "Webseite",
        st.session_state.get("company_website", ""),
    )


def role_description_page():
    lang = st.session_state.get("lang", "en")
    st.header("📋 Role Description" if lang != "de" else "📋 Stellenbeschreibung")
    st.session_state["role_summary"] = st.text_area(
        "Role Summary" if lang != "de" else "Rollenbeschreibung",
        st.session_state.get("role_summary", ""),
        height=100,
    )
    req_initial = st.session_state.get("requirements") or st.session_state.get(
        "qualifications", ""
    )
    req_text = st.text_area(
        (
            "Requirements/Qualifications"
            if lang != "de"
            else "Anforderungen/Qualifikationen"
        ),
        req_initial,
        height=100,
    )
    st.session_state["requirements"] = req_text
    st.session_state["qualifications"] = req_text


def task_scope_page():
    lang = st.session_state.get("lang", "en")
    st.header(
        "📝 Key Tasks & Responsibilities"
        if lang != "de"
        else "📝 Wichtige Aufgaben & Verantwortlichkeiten"
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
            current = tasks_text.splitlines() if tasks_text else []
            for t in suggestions:
                if t and t not in current:
                    current.append(t)
            st.session_state["tasks"] = "\n".join(current)
            st.success("✔️ Added suggested tasks.")
            st.rerun()
        else:
            st.warning("No suggestions available.")


def skills_competencies_page():
    lang = st.session_state.get("lang", "en")
    st.header(
        "🛠️ Required Skills & Competencies"
        if lang != "de"
        else "🛠️ Erforderliche Fähigkeiten & Kompetenzen"
    )
    hard_skills = st.text_area(
        "Hard/Technical Skills" if lang != "de" else "Fachliche (Hard) Skills",
        st.session_state.get("hard_skills", st.session_state.get("requirements", "")),
        height=100,
    )
    st.session_state["hard_skills"] = hard_skills
    soft_skills = st.text_area(
        "Soft Skills" if lang != "de" else "Soft Skills",
        st.session_state.get("soft_skills", ""),
        height=100,
    )
    st.session_state["soft_skills"] = soft_skills
    if st.button("💡 Suggest Additional Skills"):
        title = st.session_state.get("job_title", "")
        tasks = st.session_state.get("tasks", "")
        existing = []
        if hard_skills:
            existing += [s.strip() for s in hard_skills.splitlines() if s.strip()]
        if soft_skills:
            existing += [s.strip() for s in soft_skills.splitlines() if s.strip()]
        suggestions = suggest_additional_skills(
            title,
            tasks,
            existing,
            num_suggestions=10,
            lang=("de" if lang == "de" else "en"),
        )
        tech = suggestions.get("technical", [])
        soft = suggestions.get("soft", [])
        updated_hard = existing + [s for s in tech if s and s not in existing]
        updated_soft = [s for s in soft if s and s not in existing]
        st.session_state["hard_skills"] = "\n".join(updated_hard)
        st.session_state["soft_skills"] = "\n".join(updated_soft)
        st.success("✔️ Added skill suggestions.")
        st.rerun()


def benefits_compensation_page():
    lang = st.session_state.get("lang", "en")
    st.header(
        "💰 Benefits & Compensation" if lang != "de" else "💰 Vergütung & Vorteile"
    )
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


def recruitment_process_page():
    lang = st.session_state.get("lang", "en")
    st.header("🏁 Recruitment Process" if lang != "de" else "🏁 Einstellungsprozess")
    st.session_state["interview_stages"] = int(
        st.number_input(
            (
                "Number of Interview Rounds"
                if lang != "de"
                else "Anzahl der Interviewrunden"
            ),
            min_value=0,
            step=1,
            value=int(st.session_state.get("interview_stages", 0)),
        )
    )
    st.session_state["process_notes"] = st.text_area(
        (
            "Additional Hiring Process Notes"
            if lang != "de"
            else "Weitere Hinweise zum Prozess"
        ),
        st.session_state.get("process_notes", ""),
        height=80,
    )


def summary_outputs_page():
    lang = st.session_state.get("lang", "en")
    normalise_state(reapply_aliases=False)
    st.header(
        "📊 Summary & Outputs" if lang != "de" else "📊 Zusammenfassung & Ergebnisse"
    )
    fields = (
        ["job_title"]
        + [f for f in EXTENDED_FIELDS if f not in ALIASES]
        + [
            "hard_skills",
            "soft_skills",
        ]
    )
    seen = set()
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        value = st.session_state.get(field)
        if value:
            display = str(value).replace("\n", "; ")
            st.write(f"**{field.replace('_', ' ').title()}:** {display}")

    colA, colB = st.columns(2)
    with colA:
        if st.button("🎯 Generate Final Job Ad"):
            job_ad_text = generate_job_ad(st.session_state)
            st.subheader("Generated Job Advertisement")
            st.write(job_ad_text)
            seo = seo_optimize(job_ad_text)
            if seo["keywords"]:
                st.markdown(f"**SEO Keywords:** `{', '.join(seo['keywords'])}`")
            if seo["meta_description"]:
                st.markdown(f"**Meta Description:** {seo['meta_description']}")
            log_event(f"JOB_AD by {st.session_state.get('user', 'anonymous')}")
    with colB:
        if st.button("📝 Generate Interview Guide"):
            title = st.session_state.get("job_title", "")
            tasks = st.session_state.get("tasks", "") or st.session_state.get(
                "responsibilities", ""
            )
            guide = generate_interview_guide(
                title, tasks, audience="hiring managers", num_questions=5
            )
            st.subheader("Interview Guide & Scoring Rubrics")
            st.write(guide)
            log_event(f"INTERVIEW_GUIDE by {st.session_state.get('user', 'anonymous')}")

    if st.session_state.get("job_title") or st.session_state.get("hard_skills"):
        bool_query = build_boolean_query(
            st.session_state.get("job_title", ""),
            (
                st.session_state.get("hard_skills", "")
                + "\n"
                + st.session_state.get("soft_skills", "")
            ).splitlines(),
        )
        if bool_query:
            st.info(f"**Boolean Search Query:** `{bool_query}`")


def log_event(event_text: str):
    import datetime

    ensure_logs_dir()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {event_text}\n"
    try:
        with open("logs/usage.log", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        print(entry)
