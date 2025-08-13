import streamlit as st
from config import DEFAULT_LANGUAGE
from components.tailwind_injector import inject_tailwind
from components.salary_dashboard import render_salary_dashboard
from wizard import (
    apply_global_styling,
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
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
if "company_logo" not in st.session_state:
    st.session_state["company_logo"] = None

# Sidebar branding options
logo_file = st.sidebar.file_uploader("Company Logo", type=["png", "jpg", "jpeg"])
if logo_file:
    st.session_state["company_logo"] = logo_file.getvalue()
if st.session_state.get("company_logo"):
    st.sidebar.image(st.session_state["company_logo"], use_container_width=True)
else:
    st.sidebar.image(
        "images/color1_logo_transparent_background.png", use_container_width=True
    )
theme_choice = st.sidebar.selectbox(
    "Theme",
    ["Dark", "Light"],
    0 if st.session_state["theme"] == "dark" else 1,
)
st.session_state["theme"] = "dark" if theme_choice == "Dark" else "light"

# Inject Tailwind CSS for styling
inject_tailwind(theme=st.session_state["theme"])

# Apply global styles
apply_global_styling(theme=st.session_state["theme"])

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
sections[idx]["func"]()
show_navigation(idx, total)
render_salary_dashboard()
