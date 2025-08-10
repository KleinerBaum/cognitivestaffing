import os
import streamlit as st

# Load environment variables (if using a .env file for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Basic settings
STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")  # "en" or "de"
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")  # OpenAI model name

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

# If Streamlit secrets are provided (e.g. on Streamlit Cloud), override above
try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)
except Exception:
    openai_secrets = None

# Set the OpenAI API key globally if available
if OPENAI_API_KEY:
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
    except ImportError:
        pass

# Database URL for usage tracking (if any, e.g. PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY = os.getenv("SECRET_KEY", "replace-me")
