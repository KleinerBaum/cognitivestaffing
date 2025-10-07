# app.py — Cognitive Needs (clean entrypoint, single source of truth)
from __future__ import annotations

from base64 import b64encode
from pathlib import Path
import sys

import streamlit as st

APP_ROOT = Path(__file__).resolve().parent
for candidate in (APP_ROOT, APP_ROOT.parent):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from utils.telemetry import setup_tracing  # noqa: E402
from config_loader import load_json  # noqa: E402
from utils.i18n import tr  # noqa: E402
from state import ensure_state  # noqa: E402
from sidebar import render_sidebar  # noqa: E402

setup_tracing()

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helpers zum Laden lokaler JSON-Configs ---
ROOT = APP_ROOT
ensure_state()

if st.session_state.get("openai_api_key_missing"):
    st.warning(
        tr(
            "⚠️ OpenAI-API-Schlüssel nicht gesetzt. Bitte in der Umgebung konfigurieren, um KI-Funktionen zu nutzen.",
            "⚠️ OpenAI API key not set. Please configure it in the environment to use AI features.",
        )
    )
if st.session_state.get("openai_base_url_invalid"):
    st.warning(
        tr(
            "⚠️ OPENAI_BASE_URL scheint ungültig zu sein und wird ignoriert.",
            "⚠️ OPENAI_BASE_URL appears invalid and will be ignored.",
        )
    )


def inject_global_css() -> None:
    """Inject the global stylesheet and background image."""

    theme = (
        "cognitive_needs.css"
        if st.session_state.get("dark_mode", True)
        else "cognitive_needs_light.css"
    )
    css = (ROOT / "styles" / theme).read_text(encoding="utf-8")
    bg_bytes = (ROOT / "images" / "AdobeStock_506577005.jpeg").read_bytes()
    encoded_bg = b64encode(bg_bytes).decode()
    st.markdown(
        f"<style>{css}\n:root {{ --bg-image: url('data:image/jpeg;base64,{encoded_bg}'); }}</style>",
        unsafe_allow_html=True,
    )


inject_global_css()

SIDEBAR_STYLE = """
<style>
[data-testid="stSidebar"] .block-container {
    padding-top: 1.4rem;
}
.sidebar-hero {
    display: flex;
    gap: 0.9rem;
    align-items: center;
    padding: 1.1rem 1.2rem;
    border-radius: 1.2rem;
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.92), rgba(236, 72, 153, 0.85));
    box-shadow: 0 18px 44px rgba(15, 23, 42, 0.22);
    margin-bottom: 1.3rem;
}
.sidebar-hero__icon {
    font-size: 2.4rem;
}
.sidebar-hero__eyebrow {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.22em;
    opacity: 0.8;
    margin: 0 0 0.2rem 0;
}
.sidebar-hero__title {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
}
.sidebar-hero__subtitle {
    margin: 0.25rem 0 0;
    font-size: 0.85rem;
    opacity: 0.9;
}
.sidebar-hero * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stToggle label {
    font-weight: 600;
    letter-spacing: 0.01em;
}
[data-testid="stSidebar"] .stButton button {
    border-radius: 999px;
}
.sidebar-stepper {
    list-style: none;
    margin: 0;
    padding: 0;
}
.sidebar-step {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.25rem 0;
    font-size: 0.9rem;
}
.sidebar-step__badge {
    width: 1.6rem;
    display: inline-flex;
    justify-content: center;
}
.sidebar-step__label {
    font-weight: 600;
}
.sidebar-step__note {
    margin-left: auto;
    font-size: 0.75rem;
    color: #64748b;
}
.sidebar-step--current .sidebar-step__label {
    color: #4338ca;
}
.sidebar-step--warning .sidebar-step__note,
.sidebar-step--blocked .sidebar-step__note {
    color: #dc2626;
}
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    margin-top: 0.6rem;
    margin-bottom: 0.4rem;
}
[data-testid="stSidebar"] h4 {
    font-size: 1rem;
}
[data-testid="stSidebar"] .stMarkdown ul {
    margin-bottom: 0.5rem;
}
</style>
"""

st.markdown(SIDEBAR_STYLE, unsafe_allow_html=True)

render_sidebar()

# --- Wizard einbinden + Advantages Page via st.navigation ---
from wizard import run_wizard  # noqa: E402
from pages import advantages  # noqa: E402

wizard_page = st.Page(run_wizard, title="Wizard", icon=":material/auto_awesome:")
advantages_page = st.Page(advantages.run, title="Advantages", icon="💡")

pg = st.navigation([wizard_page, advantages_page])
pg.run()
