from __future__ import annotations
import json
import os
from typing import Dict
import streamlit as st

# Optional: use bcrypt for password hashing
try:
    import bcrypt
except Exception:  # pragma: no cover
    bcrypt = None

def _load_users() -> Dict[str, dict]:
    """Load users from Streamlit secrets or env as JSON string."""
    users_json = None
    try:
        users_json = st.secrets.get("auth", {}).get("USERS_JSON")
    except Exception:
        pass
    if not users_json:
        users_json = os.getenv("USERS_JSON", "")
    try:
        return json.loads(users_json) if users_json else {}
    except Exception:
        return {}

def _verify_password(stored_hash: str, password: str) -> bool:
    if not stored_hash or not password:
        return False
    if bcrypt is None:
        # Fallback (NOT recommended): plain compare (for dev only)
        return stored_hash == password
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False

def is_authenticated() -> bool:
    return bool(st.session_state.get("logged_in"))

def current_user() -> str | None:
    return st.session_state.get("user")

def logout_button():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()

def login_form():
    st.title("🔐 Please Log In")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        users = _load_users()
        if username in users and _verify_password(users[username].get("hash",""), password):
            st.session_state["logged_in"] = True
            st.session_state["user"] = username
            # Optional per-user defaults (e.g., language)
            if users[username].get("lang"):
                st.session_state["lang"] = users[username]["lang"]
            st.success("Welcome!")
            st.experimental_rerun()
        else:
            st.error("Invalid credentials. Please try again.")
