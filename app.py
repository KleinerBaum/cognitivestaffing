import streamlit as st
from config import DEFAULT_LANGUAGE
from components.tailwind_injector import inject_tailwind
from wizard import (
    apply_global_styling,
    show_progress_bar,
    show_navigation,
    intro_page,
    start_discovery_page,
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

# Inject Tailwind CSS for styling
inject_tailwind(theme="dark")

# Initialize session state defaults
if "skip_intro" not in st.session_state:
    st.session_state["skip_intro"] = False
if "current_section" not in st.session_state:
    st.session_state["current_section"] = 0
if st.session_state.get("skip_intro") and st.session_state["current_section"] == 0:
    st.session_state["current_section"] = 1
if "lang" not in st.session_state:
    st.session_state["lang"] = "de" if DEFAULT_LANGUAGE.startswith("de") else "en"
if "llm_model" not in st.session_state:
    st.session_state["llm_model"] = None

# Apply global styles
apply_global_styling()

# Sidebar language switcher
lang_choice = st.sidebar.selectbox(
    "Language / Sprache",
    ["English", "Deutsch"],
    0 if st.session_state["lang"] == "en" else 1,
)
st.session_state["lang"] = "de" if lang_choice == "Deutsch" else "en"

# Define wizard sections and their corresponding page functions
sections = [
    {"name": "Intro", "func": intro_page},
    {"name": "Start", "func": start_discovery_page},
    {"name": "Company Info", "func": company_information_page},
    {"name": "Role Description", "func": role_description_page},
    {"name": "Tasks", "func": task_scope_page},
    {"name": "Skills", "func": skills_competencies_page},
    {"name": "Benefits", "func": benefits_compensation_page},
    {"name": "Process", "func": recruitment_process_page},
    {"name": "Summary", "func": summary_outputs_page},
]

# Render current section
idx = st.session_state["current_section"]
total = len(sections)
offset = 1 if st.session_state.get("skip_intro") else 0
show_progress_bar(max(idx - offset, 0), total - offset)
sections[idx]["func"]()
show_navigation(idx, total)
