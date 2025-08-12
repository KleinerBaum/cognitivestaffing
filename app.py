import streamlit as st
from config import DEFAULT_LANGUAGE
from components.tailwind_injector import inject_tailwind

st.set_page_config(
    page_title="Vacalyzer - Recruitment Need Analysis",
    layout="centered",
)

# Inject Tailwind CSS for styling
inject_tailwind(theme="dark")

# Initialize session state defaults
if "lang" not in st.session_state:
    st.session_state["lang"] = "de" if DEFAULT_LANGUAGE.startswith("de") else "en"

# Sidebar language switcher
lang_choice = st.sidebar.selectbox(
    "Language / Sprache",
    ["English", "Deutsch"],
    index=0 if st.session_state["lang"] == "en" else 1,
)
st.session_state["lang"] = "de" if lang_choice == "Deutsch" else "en"

st.title("Vacalyzer")
st.write("Welcome to Vacalyzer. Use the sidebar to navigate.")
