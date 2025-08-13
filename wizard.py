import json
from pathlib import Path

import streamlit as st
from typing import Any, cast

from core.ss_bridge import from_session_state, to_session_state
from core.schema import coerce_and_fill
from utils import (
    extract_text_from_file,
    extract_text_from_url,
    merge_texts,
    build_boolean_query,
    seo_optimize,
    ensure_logs_dir,
)
from utils.export import prepare_download_data
from openai_utils import (
    call_chat_api,
    suggest_additional_skills,
    suggest_benefits,
    generate_interview_guide,
    generate_job_ad,
    extract_company_info,
)
from llm.context import build_extract_messages
from llm.client import build_extraction_function
from question_logic import CRITICAL_FIELDS, generate_followup_questions
from core import esco_utils  # Added import to use ESCO classification
from streamlit_sortables import sort_items
from nlp.bias import scan_bias_language

MODEL_OPTIONS = {
    "GPT-3.5 (fast, cheap)": "gpt-3.5-turbo",
    "GPT-4 (slow, accurate)": "gpt-4",
}


FIELD_SECTION_MAP: dict[str, int] = {
    "job_title": 1,
    "company_name": 2,
    "location": 2,
    "role_summary": 3,
    "responsibilities": 3,
    "qualifications": 5,
    "languages_required": 5,
    "certifications": 5,
    "tools_and_technologies": 5,
    "salary_range": 6,
    "job_type": 6,
    "remote_policy": 6,
}
"""Map critical field names to wizard section indices for navigation."""


def normalise_state(reapply_aliases: bool = True):
    """Normalize session state to canonical schema keys and update JSON."""
    jd = from_session_state(cast(dict[str, Any], st.session_state))
    to_session_state(jd, cast(dict[str, Any], st.session_state))
    if reapply_aliases:
        # Keep legacy alias fields in sync for UI (if needed)
        st.session_state["requirements"] = st.session_state.get("qualifications", "")
        st.session_state["tasks"] = st.session_state.get("responsibilities", "")
        st.session_state["contract_type"] = st.session_state.get("job_type", "")
    st.session_state["validated_json"] = json.dumps(
        jd.model_dump(mode="json"), indent=2, ensure_ascii=False
    )
    return jd


def apply_global_styling() -> None:
    """Apply global styling and background image to the app.

    Injects fonts, colors and a background image into the Streamlit application.
    """
    bg_path = Path("images/AdobeStock_506577005.jpeg")
    st.markdown(
        f"""
        <style>
            .stApp {{
                background: url("{bg_path.as_posix()}") no-repeat center center fixed;
                background-size: cover;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@300;400;700&display=swap');
        body, .stApp { background-color: #0b0f14; color: #e5e7eb; font-family: 'Comfortaa', sans-serif; }
        h1,h2,h3,h4 { color: #ffffff; }
        .card { background-color: #111827; padding: 1rem; border-radius: 12px; margin-bottom: 1.25rem; }
        .stButton > button { border-radius: 10px; min-height: 2.5rem; }
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] { flex-direction: column; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { width: 100%; }
            .stButton > button { width: 100%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _is_blank(value: Any) -> bool:
    """Return ``True`` if a value is empty."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def get_missing_critical_fields(max_section: int | None = None) -> list[str]:
    """List critical fields that are still empty up to ``max_section``.

    Args:
        max_section: Highest wizard section to inspect. ``None`` checks all
            sections.

    Returns:
        Sorted list of missing field names.
    """

    limit = (
        max_section
        if max_section is not None
        else max(FIELD_SECTION_MAP.values(), default=0)
    )
    missing: set[str] = set()
    for field in CRITICAL_FIELDS:
        section = FIELD_SECTION_MAP.get(field, 0)
        if section <= limit and _is_blank(st.session_state.get(field)):
            missing.add(field)

    followups = st.session_state.get("followup_questions", [])
    for item in followups:
        field = item.get("field")
        if not field or item.get("priority") != "critical":
            continue
        section = FIELD_SECTION_MAP.get(field, limit)
        if section <= limit and _is_blank(st.session_state.get(field)):
            missing.add(field)

    return sorted(missing)


def show_navigation(current_step: int, total_steps: int) -> None:
    """Render Previous/Next navigation buttons for the wizard.

    Prevents advancing while any critical field on current or previous pages
    is left blank. The intro page (step 0) hides navigation controls.
    """

    if current_step == 0:
        return

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if current_step > 0:
            if st.button("⬅ Previous"):
                st.session_state["current_section"] -= 1
                st.rerun()
    with col3:
        if current_step < total_steps - 1:
            if st.button("Next ➡"):
                missing = get_missing_critical_fields(current_step)
                if missing:
                    st.warning(
                        f"Please fill the required fields before continuing: {', '.join(missing)}"
                    )
                else:
                    st.session_state["current_section"] += 1
                    st.rerun()


def render_followups_for(fields: list[str] | None = None) -> None:
    """Display follow-up questions inline for specified fields.

    Critical questions are prefixed with a red asterisk to signal required
    input.

    Args:
        fields: List of field names relevant to the current page. If ``None``,
            all follow-up questions are considered.
    """
    followups = st.session_state.get("followup_questions", [])
    if not followups:
        return

    allowed = set(fields) if fields else None
    rank = {"critical": 0, "normal": 1, "optional": 2}
    relevant = [
        f
        for f in followups
        if not allowed or f.get("field") in allowed or not f.get("field")
    ]
    if not relevant:
        return

    relevant.sort(key=lambda item: rank.get(item.get("priority", "normal"), 1))

    for item in relevant:
        field = item.get("field", "")
        question = item.get("question", "")
        key = field or question
        is_critical = item.get("priority") == "critical"

        label = ""
        if is_critical:
            st.markdown(
                f"<span style='color:red'>* {question}</span>", unsafe_allow_html=True
            )
        else:
            label = question

        if field:
            default_val = st.session_state.get(field) or item.get("prefill", "")
            st.session_state[field] = st.text_input(label, default_val, key=key)
        else:
            _ = st.text_input(label, "", key=key)

        suggestions = item.get("suggestions") or []
        if suggestions and field:
            cols = st.columns(len(suggestions))
            for idx, (col, sugg) in enumerate(zip(cols, suggestions)):
                with col:
                    if st.button(sugg, key=f"{key}_sugg_{idx}"):
                        existing = st.session_state.get(field, "")
                        sep = "\n" if existing else ""
                        st.session_state[field] = f"{existing}{sep}{sugg}"
                        st.rerun()

    st.session_state["followup_questions"] = [
        f
        for f in followups
        if not f.get("field")
        or not st.session_state.get(f.get("field", ""), "").strip()
    ]


def editable_draggable_list(field: str, label: str) -> None:
    """Render a draggable list for newline-separated session values.

    Args:
        field: Session state key storing newline-separated values.
        label: Display label for the list.
    """
    raw = st.session_state.get(field, "")
    items = [s.strip() for s in raw.splitlines() if s.strip()]

    new_item = st.text_input(f"Add {label}", key=f"{field}_new")
    if st.button("Add", key=f"{field}_add") and new_item:
        items.append(new_item)
        st.session_state[f"{field}_new"] = ""

    if items:
        remove = st.multiselect(f"Remove {label}", items, key=f"{field}_remove")
        if remove:
            items = [i for i in items if i not in remove]
            st.session_state[f"{field}_remove"] = []
        items = sort_items(
            items, header=label, direction="vertical", key=f"{field}_sort"
        )

    st.session_state[field] = "\n".join(items)


def render_summary_input(field: str, label: str, highlight_missing: bool) -> None:
    """Render an editable input for the summary page.

    Uses a text area for multiline content and a text input for shorter values.

    Args:
        field: Session state key to render.
        label: Display label for the field.
        highlight_missing: Whether the field is required but empty.
    """
    value = st.session_state.get(field, "")
    widget = (
        st.text_area if ("\n" in str(value) or len(str(value)) > 80) else st.text_input
    )
    widget_label = f"❗ {label}" if highlight_missing else label
    widget(widget_label, value, key=field)


def intro_page() -> None:
    """Display an introductory page explaining the wizard flow."""
    lang = st.session_state.get("lang", "en")
    if lang == "de":
        st.title("Erkennen Sie Ihre Recruiting-Bedürfnisse")
        st.write(
            "Vermeiden Sie kostspielige Informationsverluste im ersten Schritt jedes Recruiting-Prozesses, sammeln Sie alle unausgesprochenen Informationen für eine spezifische Vakanz, entdecken Sie verborgene Potenziale und nutzen Sie diese auf vielfältige Weise, um nicht nur Geld und Zeit zu sparen, sondern auch das Frustrationsniveau aller Beteiligten zu senken und nachhaltigen Recruiting-Erfolg sicherzustellen."
        )
        st.subheader("Sie benötigen")
        st.markdown("- Stellenanzeige (URL oder PDF)")
        st.markdown("- Kenntnisse über Unternehmensdetails")
        st.write(
            "Der Prozess passt sich dynamisch an die von Ihnen bereitgestellten Informationen an und gestaltet die Datenerhebung individuell für Ihre spezifische Vakanz."
        )
        st.checkbox("Intro beim nächsten Mal überspringen", key="skip_intro")
        if st.button("🚀 Analyse starten"):
            st.session_state["current_section"] = 1
            st.rerun()
    else:
        st.title("Detect Your Recruitment Needs")
        st.write(
            "Avoid expensive Information Loss on the 1st Step of every Recruitment-Process, collect all unspoken information for a specific vacancy, detect hidden potentials and use it in various ways in order to not only save money, but also time, reduce the level of frustration of all involved parties and ensure sustainable recruitment-success"
        )
        st.subheader("You'll need")
        st.markdown("- Job description (URL or PDF)")
        st.markdown("- Knowledge of company details")
        st.write(
            "The Process is designed to dynamically adjust to the information you provide and tailor the gathering process to your specific Vacancy."
        )
        st.checkbox("Skip intro next time", key="skip_intro")
        if st.button("🚀 Start Discovery"):
            st.session_state["current_section"] = 1
            st.rerun()


def start_discovery_page():
    """Start page: Input job title and job ad content (URL or file) for analysis."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🔍 Start Your Analysis with Vacalyzer"
        if lang != "de"
        else "🔍 Starten Sie Ihre Analyse mit Vacalyzer"
    )
    st.caption(
        "Upload a job ad or paste a URL. We’ll extract everything we can — then ask only what’s missing."
        if lang != "de"
        else "Laden Sie eine Stellenanzeige hoch oder fügen Sie eine URL ein. Wir extrahieren alle verfügbaren Informationen und fragen nur fehlende Details ab."
    )

    if st.session_state.get("extraction_success"):
        st.success("✅ Key information extracted successfully!")
        st.session_state.pop("extraction_success")

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

    # Analyze button triggers extraction
    if st.button("🔎 Analyze"):
        with st.spinner("Analyzing the job ad with AI..."):  # Spinner for feedback
            url_text = ""
            if st.session_state.get("input_url"):
                url_text = extract_text_from_url(st.session_state["input_url"])
                if not url_text:
                    st.warning(
                        "⚠️ Unable to fetch or parse content from the provided URL."
                    )
            file_text = st.session_state.get("uploaded_text", "")
            combined_text = merge_texts(url_text, file_text)
            # If no text source but job title is provided, use job title as fallback text
            if st.session_state.get("job_title") and not combined_text:
                combined_text = st.session_state["job_title"]

            if not combined_text:
                st.warning(
                    "⚠️ No text available to analyze. Please provide a job ad URL or upload a document."
                )
                return

            # Build messages and function schema for structured extraction
            messages = build_extract_messages(combined_text)
            fn_schema = build_extraction_function()
            try:
                response = call_chat_api(
                    messages,
                    model=st.session_state.get("llm_model"),
                    temperature=0.0,
                    functions=[fn_schema],
                    function_call={"name": fn_schema["name"]},
                )
            except Exception:  # pragma: no cover - network failure
                st.session_state["extraction_success"] = False
                err_msg = (
                    "❌ OpenAI request failed. Please try again later."
                    if lang != "de"
                    else "❌ OpenAI-Anfrage fehlgeschlagen. Bitte später erneut versuchen."
                )
                st.error(err_msg)
                return
            try:
                data = coerce_and_fill(json.loads(response)).model_dump(mode="json")
                # Update session state with extracted values
                for key, val in data.items():
                    # Join lists into newline-separated strings for text areas
                    st.session_state[key] = (
                        "\n".join(val) if isinstance(val, list) else str(val)
                    )
                normalise_state()  # normalize keys and prepare validated JSON
                # Generate follow-up questions for missing info
                try:
                    followups = generate_followup_questions(
                        st.session_state,
                        lang=lang,
                        use_rag=st.session_state.get("use_rag", True),
                    )
                except Exception:  # pragma: no cover - network failure
                    warn_msg = (
                        "⚠️ Unable to generate follow-up questions."
                        if lang != "de"
                        else "⚠️ Folgefragen konnten nicht erstellt werden."
                    )
                    st.warning(warn_msg)
                    followups = []
                st.session_state["followup_questions"] = followups
                # Classify occupation via ESCO and store for later display
                occ = esco_utils.classify_occupation(
                    st.session_state.get("job_title", ""), lang=lang
                )
                if occ:
                    st.session_state["occupation_label"] = occ.get(
                        "preferredLabel"
                    ) or occ.get("occupation_label", "")
                    st.session_state["occupation_group"] = occ.get("group", "")
                st.session_state["extraction_success"] = True
                # Log event (analytics)
                log_event(
                    f"ANALYZE by {st.session_state.get('user', 'anonymous')} title='{st.session_state.get('job_title', '')}'"
                )
            except Exception:
                st.session_state["extraction_success"] = False
                st.error(
                    "❌ Could not parse AI response as JSON. Please try again or rephrase the input."
                )
        # After processing, move to next section
        if st.session_state.get("extraction_success"):
            st.session_state["current_section"] = 1
            st.rerun()


def company_information_page():
    """Company Info page: Gather basic company information and optionally auto-fetch details from website."""
    lang = st.session_state.get("lang", "en")
    st.header("🏢 Company Information" if lang != "de" else "🏢 Firmeninformationen")
    try:
        st.session_state["followup_questions"] = [
            f
            for f in generate_followup_questions(
                st.session_state,
                lang=lang,
                use_rag=st.session_state.get("use_rag", True),
            )
            if f.get("field") not in {"company_mission", "company_culture"}
        ]
    except Exception:  # pragma: no cover - network failure
        pass
    render_followups_for(["company_name", "industry", "location", "company_website"])
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
        with st.spinner("Fetching company information..."):
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
                    try:
                        info = extract_company_info(combined_site_text)
                    except Exception:  # pragma: no cover - network failure
                        err = (
                            "❌ Failed to extract company information. Please try again later."
                            if lang != "de"
                            else "❌ Unternehmensinformationen konnten nicht extrahiert werden. Bitte später erneut versuchen."
                        )
                        st.error(err)
                        info = {}
                    # Update session state with any info found (if fields were empty or not set by user yet)
                    if info.get("company_name") and not st.session_state.get(
                        "company_name"
                    ):
                        st.session_state["company_name"] = info["company_name"]
                    if info.get("location") and not st.session_state.get("location"):
                        st.session_state["location"] = info["location"]
                    if info.get("company_mission"):
                        st.session_state["company_mission"] = info["company_mission"]
                    if info.get("company_culture"):
                        st.session_state["company_culture"] = info["company_culture"]
                    st.success("✅ Company information fetched from website.")
                    st.session_state["followup_questions"] = [
                        f
                        for f in st.session_state.get("followup_questions", [])
                        if f.get("field") not in {"company_mission", "company_culture"}
                    ]

    st.session_state["company_mission"] = st.text_area(
        "Company Mission" if lang != "de" else "Unternehmensmission",
        st.session_state.get("company_mission", ""),
        height=80,
    )
    st.session_state["company_culture"] = st.text_area(
        "Company Culture" if lang != "de" else "Unternehmenskultur",
        st.session_state.get("company_culture", ""),
        height=80,
    )


def role_description_page():
    """Role Description page: Summary of the role and key responsibilities."""
    lang = st.session_state.get("lang", "en")
    st.header("📋 Role Description" if lang != "de" else "📋 Rollenbeschreibung")
    try:
        st.session_state["followup_questions"] = generate_followup_questions(
            st.session_state,
            lang=lang,
            use_rag=st.session_state.get("use_rag", True),
        )
    except Exception:  # pragma: no cover - network failure
        pass
    render_followups_for(["role_summary", "responsibilities"])
    st.session_state["role_summary"] = st.text_area(
        "Role Summary / Objective" if lang != "de" else "Rollenübersicht / Ziel",
        st.session_state.get("role_summary", ""),
        height=100,
    )
    responsibilities_label = (
        "Key Responsibilities" if lang != "de" else "Hauptverantwortlichkeiten"
    )
    editable_draggable_list("responsibilities", responsibilities_label)


def task_scope_page():
    """Tasks page: Scope of tasks or projects for the role."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🗒️ Project/Task Scope" if lang != "de" else "🗒️ Projekt- / Aufgabenbereich"
    )
    render_followups_for(["tasks"])
    st.session_state["tasks"] = st.text_area(
        (
            "Main Tasks or Projects"
            if lang != "de"
            else "Wichtigste Aufgaben oder Projekte"
        ),
        st.session_state.get("tasks", ""),
        height=120,
    )


def skills_competencies_page():
    """Skills page: Required hard and soft skills, with AI suggestions to enrich the list."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "🛠️ Required Skills & Competencies"
        if lang != "de"
        else "🛠️ Erforderliche Fähigkeiten & Kompetenzen"
    )
    render_followups_for(["hard_skills", "soft_skills"])
    if not st.session_state.get("hard_skills") and st.session_state.get("requirements"):
        st.session_state["hard_skills"] = st.session_state.get("requirements", "")
    hard_label = "Hard/Technical Skills" if lang != "de" else "Fachliche (Hard) Skills"
    soft_label = "Soft Skills" if lang != "de" else "Soft Skills"
    editable_draggable_list("hard_skills", hard_label)
    editable_draggable_list("soft_skills", soft_label)
    hard_skills_text = st.session_state.get("hard_skills", "")
    soft_skills_text = st.session_state.get("soft_skills", "")
    skill_btn_col, skill_model_col = st.columns([3, 2])
    with skill_model_col:
        skill_model_label = st.selectbox(
            "Model",
            list(MODEL_OPTIONS.keys()),
            key="skill_model",
        )
    with skill_btn_col:
        if st.button("💡 Suggest Additional Skills"):
            model_name = MODEL_OPTIONS[skill_model_label]
            # Use AI to suggest additional technical and soft skills
            with st.spinner(
                f"Generating skill suggestions with {skill_model_label}..."
            ):
                title = st.session_state.get("job_title", "")
                tasks = st.session_state.get("tasks", "") or st.session_state.get(
                    "responsibilities", ""
                )
                existing_skills = []
                if hard_skills_text:
                    existing_skills += [
                        s.strip() for s in hard_skills_text.splitlines() if s.strip()
                    ]
                if soft_skills_text:
                    existing_skills += [
                        s.strip() for s in soft_skills_text.splitlines() if s.strip()
                    ]
                try:
                    suggestions = suggest_additional_skills(
                        job_title=title,
                        tasks=tasks,
                        existing_skills=existing_skills,
                        num_suggestions=10,
                        lang="de" if lang == "de" else "en",
                        model=model_name,
                    )
                except Exception:  # pragma: no cover - network failure
                    warn = (
                        "⚠️ Could not generate skill suggestions."
                        if lang != "de"
                        else "⚠️ Konnte keine Skill-Vorschläge generieren."
                    )
                    st.warning(warn)
                    suggestions = {"technical": [], "soft": []}
                tech_suggestions = suggestions.get("technical", [])
                soft_suggestions = suggestions.get("soft", [])
                # Store suggestions in session state to display as chips
                st.session_state["suggested_tech_skills"] = tech_suggestions
                st.session_state["suggested_soft_skills"] = soft_suggestions
        # Notify user to pick from suggestions
        if st.session_state.get("suggested_tech_skills") or st.session_state.get(
            "suggested_soft_skills"
        ):
            st.success(
                "✔️ Skill suggestions generated. Click on a suggestion to add it."
            )
    # If suggestions are available, display them as chips for selection
    tech_list = st.session_state.get("suggested_tech_skills", [])
    soft_list = st.session_state.get("suggested_soft_skills", [])
    if tech_list:
        st.caption("**Suggested Technical Skills:**")
        cols = st.columns(len(tech_list))
        for i, (col, skill) in enumerate(zip(cols, tech_list)):
            with col:
                if st.button(skill, key=f"tech_sugg_{i}"):
                    # Append to hard skills
                    current = st.session_state.get("hard_skills", "")
                    sep = "\n" if current else ""
                    if skill not in current:
                        st.session_state["hard_skills"] = f"{current}{sep}{skill}"
                    # Remove the added skill from suggestions
                    st.session_state["suggested_tech_skills"] = [
                        s for s in tech_list if s != skill
                    ]
                    st.rerun()
    if soft_list:
        st.caption("**Suggested Soft Skills:**")
        cols = st.columns(len(soft_list))
        for j, (col, skill) in enumerate(zip(cols, soft_list)):
            with col:
                if st.button(skill, key=f"soft_sugg_{j}"):
                    # Append to soft skills
                    current = st.session_state.get("soft_skills", "")
                    sep = "\n" if current else ""
                    if skill not in current:
                        st.session_state["soft_skills"] = f"{current}{sep}{skill}"
                    st.session_state["suggested_soft_skills"] = [
                        s for s in soft_list if s != skill
                    ]
                    st.rerun()


def benefits_compensation_page():
    """Benefits page: Compensation and benefits details, with suggestions for perks."""
    lang = st.session_state.get("lang", "en")
    st.header(
        "💰 Benefits & Compensation" if lang != "de" else "💰 Vergütung & Vorteile"
    )
    render_followups_for(
        [
            "salary_range",
            "benefits",
            "health_benefits",
            "retirement_benefits",
            "learning_opportunities",
            "remote_policy",
            "travel_required",
        ]
    )
    st.session_state["salary_range"] = st.text_input(
        "Salary Range" if lang != "de" else "Gehaltsspanne",
        st.session_state.get("salary_range", ""),
    )
    benefits_label = "Benefits/Perks" if lang != "de" else "Vorteile/Extras"
    health_label = "Healthcare Benefits" if lang != "de" else "Gesundheitsleistungen"
    retirement_label = "Retirement Benefits" if lang != "de" else "Altersvorsorge"
    editable_draggable_list("benefits", benefits_label)
    editable_draggable_list("health_benefits", health_label)
    editable_draggable_list("retirement_benefits", retirement_label)
    st.session_state["learning_opportunities"] = st.text_area(
        (
            "Learning & Development Opportunities"
            if lang != "de"
            else "Weiterbildungs- und Entwicklungsmöglichkeiten"
        ),
        st.session_state.get("learning_opportunities", ""),
        height=70,
    )
    st.session_state["remote_policy"] = st.text_input(
        "Remote Work Policy" if lang != "de" else "Richtlinie für Fernarbeit",
        st.session_state.get("remote_policy", ""),
    )
    st.session_state["travel_required"] = st.text_input(
        "Travel Requirements" if lang != "de" else "Reisebereitschaft",
        st.session_state.get("travel_required", ""),
    )
    benefit_btn_col, benefit_model_col = st.columns([3, 2])
    with benefit_model_col:
        benefit_model_label = st.selectbox(
            "Model",
            list(MODEL_OPTIONS.keys()),
            key="benefit_model",
        )
    with benefit_btn_col:
        if st.button("💡 Suggest Benefits"):
            model_name = MODEL_OPTIONS[benefit_model_label]
            with st.spinner(
                f"Suggesting common benefits with {benefit_model_label}..."
            ):
                title = st.session_state.get("job_title", "")
                industry = st.session_state.get("industry", "")
                existing = st.session_state.get("benefits", "")
                try:
                    suggestions = suggest_benefits(
                        title,
                        industry,
                        existing_benefits=existing,
                        model=model_name,
                    )
                except Exception:  # pragma: no cover - network failure
                    warn = (
                        "⚠️ Could not generate benefit suggestions."
                        if lang != "de"
                        else "⚠️ Konnte keine Benefit-Vorschläge generieren."
                    )
                    st.warning(warn)
                    suggestions = []
            if suggestions:
                st.session_state["suggested_benefits"] = suggestions
                st.success("✔️ Benefit suggestions generated. Click to add them.")
            else:
                st.warning("No benefit suggestions available at the moment.")
    # Display benefit suggestions as chips if available
    benefit_suggestions = st.session_state.get("suggested_benefits", [])
    if benefit_suggestions:
        cols = st.columns(len(benefit_suggestions))
        for k, (col, perk) in enumerate(zip(cols, benefit_suggestions)):
            with col:
                if st.button(perk, key=f"benefit_sugg_{k}"):
                    current = st.session_state.get("benefits", "")
                    sep = "\n" if current else ""
                    if perk not in current:
                        st.session_state["benefits"] = f"{current}{sep}{perk}"
                    # Remove added perk from suggestions list
                    st.session_state["suggested_benefits"] = [
                        b for b in benefit_suggestions if b != perk
                    ]
                    st.rerun()


def recruitment_process_page():
    """Process page: Details about the recruitment process (interview rounds, notes)."""
    lang = st.session_state.get("lang", "en")
    st.header("🏁 Recruitment Process" if lang != "de" else "🏁 Einstellungsprozess")
    render_followups_for(["interview_stages", "process_notes"])
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
    """Summary page: Display a summary of collected fields and provide output generation (job ad, interview guide, boolean query)."""
    lang = st.session_state.get("lang", "en")
    normalise_state(
        reapply_aliases=False
    )  # Final normalization (do not reapply alias values here)
    st.header(
        "📊 Summary & Outputs" if lang != "de" else "📊 Zusammenfassung & Ergebnisse"
    )
    # Show ESCO occupation classification if available
    if st.session_state.get("occupation_label"):
        occ_label = st.session_state["occupation_label"]
        occ_group = st.session_state.get("occupation_group", "")
        if lang == "de":
            st.write(f"**Erkannte ESCO-Berufsgruppe:** {occ_label} ({occ_group})")
        else:
            st.write(f"**Identified ESCO Occupation:** {occ_label} ({occ_group})")
    categories = [
        {
            "en": "Company & Context",
            "de": "Unternehmen & Kontext",
            "fields": [
                "company_name",
                "company_website",
                "industry",
                "location",
                "company_mission",
                "company_culture",
            ],
        },
        {
            "en": "Role Details",
            "de": "Rollenbeschreibung",
            "fields": [
                "job_title",
                "role_summary",
                "responsibilities",
                "tasks",
                "department",
                "team_structure",
                "reporting_line",
            ],
        },
        {
            "en": "Requirements",
            "de": "Anforderungen",
            "fields": [
                "qualifications",
                "hard_skills",
                "soft_skills",
                "tools_and_technologies",
                "languages_required",
                "certifications",
                "seniority_level",
            ],
        },
        {
            "en": "Benefits & Conditions",
            "de": "Leistungen & Konditionen",
            "fields": [
                "job_type",
                "remote_policy",
                "onsite_requirements",
                "travel_required",
                "working_hours",
                "salary_range",
                "bonus_compensation",
                "benefits",
                "health_benefits",
                "retirement_benefits",
                "learning_opportunities",
                "equity_options",
                "relocation_assistance",
                "visa_sponsorship",
            ],
        },
        {
            "en": "Process",
            "de": "Prozess",
            "fields": [
                "target_start_date",
                "application_deadline",
                "performance_metrics",
                "interview_stages",
                "process_notes",
            ],
        },
    ]
    for category in categories:
        rendered_heading = False
        for field in category["fields"]:
            value = st.session_state.get(field, "")
            is_missing = not value and field in CRITICAL_FIELDS
            if value or is_missing:
                if not rendered_heading:
                    heading = category["de"] if lang == "de" else category["en"]
                    st.subheader(heading)
                    rendered_heading = True
                label = field.replace("_", " ").title()
                render_summary_input(field, label, is_missing)
    # Buttons to generate final outputs
    colA, colB = st.columns(2)
    with colA:
        if st.button("🎯 Generate Final Job Ad"):
            with st.spinner("Generating job advertisement..."):
                try:
                    job_ad_text = generate_job_ad(st.session_state)
                except Exception:  # pragma: no cover - network failure
                    err = (
                        "❌ Failed to generate job ad. Please try again later."
                        if lang != "de"
                        else "❌ Stellenanzeige konnte nicht erstellt werden. Bitte später erneut versuchen."
                    )
                    st.error(err)
                    job_ad_text = ""
            if job_ad_text:
                st.subheader(
                    (
                        "Generated Job Advertisement"
                        if lang != "de"
                        else "Erstellte Stellenanzeige"
                    ),
                )
                st.write(job_ad_text)
                findings = scan_bias_language(job_ad_text, lang)
                if findings:
                    warn = (
                        "Potentially biased terms detected:"
                        if lang != "de"
                        else "Möglicherweise vorbelastete Begriffe gefunden:"
                    )
                    st.warning(warn)
                    for item in findings:
                        st.markdown(f"- `{item['term']}` → {item['suggestion']}")
                # Basic SEO optimization suggestions for the generated ad
                seo = seo_optimize(job_ad_text)
                if seo["keywords"]:
                    st.markdown(f"**SEO Keywords:** `{', '.join(seo['keywords'])}`")
                if seo["meta_description"]:
                    st.markdown(f"**Meta Description:** {seo['meta_description']}")
                fmt_label = "Download format" if lang != "de" else "Download-Format"
                job_fmt = st.selectbox(
                    fmt_label,
                    ["markdown", "docx", "pdf", "json"],
                    key="job_ad_format",
                )
                data, mime, ext = prepare_download_data(
                    job_ad_text,
                    job_fmt,
                    key="job_ad",
                    title=st.session_state.get("job_title"),
                )
                dl_label = (
                    "💾 Download Job Ad"
                    if lang != "de"
                    else "💾 Stellenanzeige herunterladen"
                )
                st.download_button(
                    dl_label,
                    data=data,
                    file_name=f"job_ad.{ext}",
                    mime=mime,
                )
                log_event(f"JOB_AD by {st.session_state.get('user', 'anonymous')}")
    with colB:
        q_label = (
            "Number of interview questions"
            if lang != "de"
            else "Anzahl der Interviewfragen"
        )
        num_questions = st.slider(
            q_label,
            min_value=3,
            max_value=10,
            value=5,
            key="num_questions",
        )
        if st.button("📝 Generate Interview Guide"):
            title = st.session_state.get("job_title", "")
            tasks = st.session_state.get("tasks", "") or st.session_state.get(
                "responsibilities",
                "",
            )
            with st.spinner("Generating interview guide..."):
                try:
                    guide = generate_interview_guide(
                        title,
                        tasks,
                        audience="hiring managers",
                        num_questions=num_questions,
                        lang=lang,
                        company_culture=st.session_state.get("company_culture", ""),
                    )
                except Exception:  # pragma: no cover - network failure
                    err = (
                        "❌ Failed to generate interview guide. Please try again later."
                        if lang != "de"
                        else "❌ Leitfaden konnte nicht erstellt werden. Bitte später erneut versuchen."
                    )
                    st.error(err)
                    guide = ""
            if guide:
                st.subheader(
                    (
                        "Interview Guide & Scoring Rubrics"
                        if lang != "de"
                        else "Leitfaden für Vorstellungsgespräch & Bewertungsrichtlinien"
                    ),
                )
                st.write(guide)
                fmt_label = "Download format" if lang != "de" else "Download-Format"
                guide_fmt = st.selectbox(
                    fmt_label,
                    ["markdown", "docx", "pdf", "json"],
                    key="guide_format",
                )
                data, mime, ext = prepare_download_data(
                    guide,
                    guide_fmt,
                    key="interview_guide",
                    title=st.session_state.get("job_title"),
                )
                dl_label = (
                    "💾 Download Interview Guide"
                    if lang != "de"
                    else "💾 Leitfaden herunterladen"
                )
                st.download_button(
                    dl_label,
                    data=data,
                    file_name=f"interview_guide.{ext}",
                    mime=mime,
                )
                log_event(
                    f"INTERVIEW_GUIDE by {st.session_state.get('user', 'anonymous')}"
                )
    # Always display a suggested Boolean search query for recruiters
    if st.session_state.get("job_title") or st.session_state.get("hard_skills"):
        skills = (
            st.session_state.get("hard_skills", "")
            + "\n"
            + st.session_state.get("soft_skills", "")
        ).splitlines()
        skills = [s.strip() for s in skills if s.strip()]
        with st.expander(
            "Customize Boolean Search" if lang != "de" else "Boolean-Suche anpassen"
        ):
            include_title = st.checkbox(
                "Include job title" if lang != "de" else "Jobtitel einbeziehen",
                value=bool(st.session_state.get("job_title")),
            )
            title_synonyms_input = st.text_input(
                (
                    "Title synonyms (comma-separated)"
                    if lang != "de"
                    else "Titel-Synonyme (durch Komma getrennt)"
                ),
            )
            selected_skills = st.multiselect(
                "Skills to include" if lang != "de" else "Skills einbeziehen",
                options=skills,
                default=skills,
            )
        bool_query = build_boolean_query(
            st.session_state.get("job_title", ""),
            selected_skills,
            include_title=include_title,
            title_synonyms=[
                s.strip() for s in title_synonyms_input.split(",") if s.strip()
            ],
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
