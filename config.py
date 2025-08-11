import os
import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

STREAMLIT_ENV = os.getenv("STREAMLIT_ENV", "development")
DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
OPENAI_MODEL_HIGH = os.getenv("OPENAI_MODEL_HIGH", "gpt-4o")

try:
    openai_secrets = st.secrets["openai"]
    OPENAI_API_KEY = openai_secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_MODEL = openai_secrets.get("OPENAI_MODEL", OPENAI_MODEL)
    OPENAI_MODEL_HIGH = openai_secrets.get("OPENAI_MODEL_HIGH", OPENAI_MODEL_HIGH)
except Exception:
    openai_secrets = None

if OPENAI_API_KEY:
    try:
        import openai

        openai.api_key = OPENAI_API_KEY
    except ImportError:
        pass

DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY = os.getenv("SECRET_KEY", "replace-me")
