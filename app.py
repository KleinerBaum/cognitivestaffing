# app.py — Vacalyser (clean entrypoint, single source of truth)
from __future__ import annotations

from pathlib import Path
from base64 import b64encode

import streamlit as st

from components.salary_dashboard import render_salary_dashboard
from config_loader import load_json
from utils.i18n import tr
from state.ensure_state import ensure_state

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Vacalyser — AI Recruitment Need Analysis",
    page_icon="🧭",
    layout="wide",
)

# --- Helpers zum Laden lokaler JSON-Configs ---
ROOT = Path(__file__).parent
ensure_state()


def inject_global_css() -> None:
    """Inject the global stylesheet and background image.

    Reads the CSS theme and background image, encodes the image in base64,
    and sets the `--bg-image` variable so the app renders a hero background.
    """

    css = (ROOT / "styles" / "vacalyser.css").read_text(encoding="utf-8")
    bg_bytes = (ROOT / "images" / "AdobeStock_506577005.jpeg").read_bytes()
    encoded_bg = b64encode(bg_bytes).decode()
    st.markdown(
        f"<style>{css}\n:root {{ --bg-image: url('data:image/jpeg;base64,{encoded_bg}'); }}</style>",
        unsafe_allow_html=True,
    )


inject_global_css()

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

# --- Warnung bei vorhandenem pages/-Ordner (wird trotzdem ignoriert, da st.navigation aktiv ist) ---
if (ROOT / "pages").exists():
    st.sidebar.info(
        tr(
            "Hinweis: Ein 'pages/'-Ordner wurde erkannt. Diese App nutzt `st.navigation`, daher wird 'pages/' ignoriert.",
            "Note: A 'pages/' directory was detected. This app uses `st.navigation`, so 'pages/' is ignored.",
        ),
        icon="ℹ️",
    )

# --- Sidebar: globale Controls ---
with st.sidebar:
    st.markdown(tr("### ⚙️ Einstellungen", "### ⚙️ Settings"))
    st.session_state.lang = st.selectbox(
        tr("Sprache", "Language"),
        ["de", "en"],
        index=(0 if st.session_state.lang == "de" else 1),
    )
    st.session_state.auto_reask = st.toggle(
        "Auto Follow-ups", value=st.session_state.auto_reask
    )
    st.session_state.model = st.text_input("OpenAI Model", value=st.session_state.model)
    st.session_state.vector_store_id = st.text_input(
        "Vector Store ID (optional)", value=st.session_state.vector_store_id
    )

    if st.button("🔁 Reset Wizard", type="secondary"):
        for k in list(st.session_state.keys()):
            if k not in ("lang", "model", "vector_store_id", "auto_reask"):
                del st.session_state[k]
        ensure_state()
        st.success(tr("Wizard wurde zurückgesetzt.", "Wizard has been reset."))

render_salary_dashboard(st.session_state)

# --- Wizard einbinden als einzelne Page via st.navigation (verhindert pages/-Konflikte) ---
from wizard import run_wizard  # unsere neue Wizard-Funktion (siehe unten)  # noqa: E402

wizard_page = st.Page(run_wizard, title="Wizard", icon=":material/auto_awesome:")

# Optional: später weitere Pages (z. B. „About“) hinzufügen:
# about_page = st.Page(about.run, title="About", icon=":material/info:")

pg = st.navigation([wizard_page])  # Sidebar/Topbar Navigation (nur 1 Page)
pg.run()
