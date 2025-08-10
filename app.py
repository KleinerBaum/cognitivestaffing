import streamlit as st
from config import DEFAULT_LANGUAGE
from components.tailwind_injector import inject_tailwind
from wizard import (apply_global_styling, show_progress_bar, show_navigation,
                    start_discovery_page, company_information_page, role_description_page,
                    task_scope_page, skills_competencies_page, benefits_compensation_page,
                    recruitment_process_page, summary_outputs_page)

# Configure page
st.set_page_config(page_title="Vacalyzer - Recruitment Need Analysis", layout="centered")

# Inject Tailwind & theme at the top of every run
inject_tailwind(theme="dark")

# Initialize session state for multi-page navigation
if "current_section" not in st.session_state:
    st.session_state["current_section"] = 0
if "lang" not in st.session_state:
    st.session_state["lang"] = "de" if DEFAULT_LANGUAGE.startswith("de") else "en"
if "llm_model" not in st.session_state:
    st.session_state["llm_model"] = None

# User Authentication / Login
if "logged_in" not in st.session_state or st.session_state.get("logged_in") is False:
    st.session_state["logged_in"] = False
    st.title("🔐 Please Log In")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        VALID_USERS = {"admin": "pass123", "user1": "password1"}
        if username in VALID_USERS and password == VALID_USERS[username]:
            st.session_state["logged_in"] = True
            st.session_state["user"] = username
            st.experimental_rerun()
        else:
            st.error("Invalid credentials. Please try again.")
    st.stop()

# Apply additional global styling (complements Tailwind)
apply_global_styling()

# Language selector
lang_choice = st.sidebar.selectbox("Language / Sprache", ["English", "Deutsch"],
                                   0 if st.session_state["lang"] == "en" else 1)
st.session_state["lang"] = "de" if lang_choice == "Deutsch" else "en"

# Steps
sections = [
    {"name": "Start", "func": start_discovery_page},
    {"name": "Company Info", "func": company_information_page},
    {"name": "Role Description", "func": role_description_page},
    {"name": "Tasks", "func": task_scope_page},
    {"name": "Skills", "func": skills_competencies_page},
    {"name": "Benefits", "func": benefits_compensation_page},
    {"name": "Process", "func": recruitment_process_page},
    {"name": "Summary", "func": summary_outputs_page},
]

current_idx = st.session_state["current_section"]
total_sections = len(sections)

# Progress
show_progress_bar(current_idx, total_sections)

# Render current
sections[current_idx]["func"]()

# Navigation
show_navigation(current_idx, total_sections)
