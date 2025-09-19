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

from constants.keys import UIKeys  # noqa: E402
from config_loader import load_json  # noqa: E402
from utils.i18n import tr  # noqa: E402
from state import ensure_state  # noqa: E402

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
.sidebar-note {
    font-size: 0.82rem;
    line-height: 1.45;
    padding: 0.75rem 0.9rem;
    border-radius: 0.85rem;
    background: rgba(15, 23, 42, 0.04);
    border: 1px solid rgba(148, 163, 184, 0.35);
    margin-top: 0.8rem;
}
</style>
"""

st.markdown(SIDEBAR_STYLE, unsafe_allow_html=True)


def render_primary_sidebar() -> None:
    """Render the redesigned global sidebar."""

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")
    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]
    if "ui.dark_mode" not in st.session_state:
        st.session_state["ui.dark_mode"] = st.session_state.get("dark_mode", True)

    def _on_theme_toggle() -> None:
        st.session_state["dark_mode"] = st.session_state["ui.dark_mode"]

    def _on_lang_change() -> None:
        st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    lang_options = {"de": "DE", "en": "EN"}

    hero_title = tr("Dein Recruiting-Co-Pilot", "Your recruiting co-pilot")
    hero_subtitle = tr(
        "Verwalte Einstellungen wie im vertrauten ATS – klar, fokussiert, jederzeit erreichbar.",
        "Manage your essentials like in your familiar ATS – clear, focused and always within reach.",
    )
    status_label = tr("Wizard-Status", "Wizard status")

    with st.sidebar:
        st.markdown(f"### ⚙️ {tr('Einstellungen', 'Settings')}")
        st.toggle("Dark Mode 🌙", key="ui.dark_mode", on_change=_on_theme_toggle)
        st.radio(
            tr("Sprache", "Language"),
            options=list(lang_options.keys()),
            key=UIKeys.LANG_SELECT,
            horizontal=True,
            format_func=lambda key: lang_options[key],
            on_change=_on_lang_change,
        )

        st.markdown(
            f"""
            <div class="sidebar-hero">
              <div class="sidebar-hero__icon">🧭</div>
              <div>
                <p class="sidebar-hero__eyebrow">{status_label}</p>
                <h2 class="sidebar-hero__title">{hero_title}</h2>
                <p class="sidebar-hero__subtitle">{hero_subtitle}</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.markdown(f"### 💡 {tr('Tipps aus der Praxis', 'Practical tips')}")
        st.markdown(
            tr(
                "- Durchlaufe den Wizard Schritt für Schritt – deine Eingaben bleiben erhalten.\n"
                "- Alle KI-Ergebnisse findest du gesammelt in der Summary.",
                "- Move through the wizard step by step – your inputs remain persistent.\n"
                "- Find every AI result again in the summary view.",
            )
        )


SCHEMA = load_json("schema/need_analysis.schema.json", fallback={})
CRITICAL = set(
    load_json("critical_fields.json", fallback={"critical": []}).get("critical", [])
)
TONE = load_json("tone_presets.json", fallback={"en": {}, "de": {}})
ROLE_FIELD_MAP = load_json("role_field_map.json", fallback={})


# --- Headbar / Branding minimal & konfliktfrei ---
st.markdown(
    """
    <style>
      .block-container { padding-top: 1rem; }
      header { visibility: hidden; } /* Prevent default Streamlit header */
    </style>
    """,
    unsafe_allow_html=True,
)

render_primary_sidebar()

# --- Wizard einbinden + Advantages Page via st.navigation ---
from wizard import run_wizard  # noqa: E402
from pages import advantages  # noqa: E402

wizard_page = st.Page(run_wizard, title="Wizard", icon=":material/auto_awesome:")
advantages_page = st.Page(advantages.run, title="Advantages", icon="💡")

pg = st.navigation([wizard_page, advantages_page])
pg.run()
