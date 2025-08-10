import streamlit as st
from config import DEFAULT_LANGUAGE
from components.tailwind_injector import inject_tailwind
from wizard import (
    apply_global_styling,
    show_progress_bar,
    show_navigation,
    start_discovery_page,
    followup_questions_page,
    company_information_page,
    role_description_page,
    task_scope_page,
    skills_competencies_page,
    benefits_compensation_page,
    recruitment_process_page,
    summary_outputs_page,
)

st.set_page_config(
    page_title="Vacalyzer - Recruitment Need Analysis",
    layout="centered",
)

# Tailwind
inject_tailwind(theme="dark")

# Init session defaults
if "current_section" not in st.session_state:
    st.session_state["current_section"] = 0
if "lang" not in st.session_state:
    st.session_state["lang"] = "de" if DEFAULT_LANGUAGE.startswith("de") else "en"  # noqa: E501
if "llm_model" not in st.session_state:
    st.session_state["llm_model"] = None

# Styling
apply_global_styling()

# Sidebar: Language switch
lang_choice = st.sidebar.selectbox(
    "Language / Sprache",
    ["English", "Deutsch"],
    0 if st.session_state["lang"] == "en" else 1,
)
st.session_state["lang"] = "de" if lang_choice == "Deutsch" else "en"

# Wizard steps
sections = [
    {"name": "Start", "func": start_discovery_page},
    {"name": "Follow-Ups", "func": followup_questions_page},
    {"name": "Company Info", "func": company_information_page},
    {"name": "Role Description", "func": role_description_page},
    {"name": "Tasks", "func": task_scope_page},
    {"name": "Skills", "func": skills_competencies_page},
    {"name": "Benefits", "func": benefits_compensation_page},
    {"name": "Process", "func": recruitment_process_page},
    {"name": "Summary", "func": summary_outputs_page},
]

idx = st.session_state["current_section"]
total = len(sections)

show_progress_bar(idx, total)
sections[idx]["func"]()
show_navigation(idx, total)
