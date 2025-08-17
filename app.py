# app.py — Vacalyser (clean entrypoint, single source of truth)
from __future__ import annotations

import json
import os
from pathlib import Path
import streamlit as st

from components.salary_dashboard import render_salary_dashboard
from utils.i18n import tr

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Vacalyser — AI Recruitment Need Analysis",
    page_icon="🧭",
    layout="wide",
)

# --- Helpers zum Laden lokaler JSON-Configs ---
ROOT = Path(__file__).parent


def _load_json(path: Path, fallback: dict | None = None) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback or {}


SCHEMA = _load_json(ROOT / "vacalyser_schema.json", fallback={})
CRITICAL = set(
    _load_json(ROOT / "critical_fields.json", fallback={"critical": []}).get(
        "critical", []
    )
)
TONE = _load_json(ROOT / "tone_presets.json", fallback={"en": {}, "de": {}})
ROLE_FIELD_MAP = _load_json(ROOT / "role_field_map.json", fallback={})


# --- Session Defaults (einheitliche Keys) ---
def _init_state():
    ss = st.session_state
    ss.setdefault("data", {})  # entspricht vacalyser_schema.json
    ss.setdefault("lang", "de")  # "de" | "en"
    ss.setdefault("model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    ss.setdefault("vector_store_id", os.getenv("VECTOR_STORE_ID") or "")
    ss.setdefault("auto_reask", True)  # auto Follow-ups?
    ss.setdefault("step", 0)  # Wizard step index
    ss.setdefault("usage", {"input_tokens": 0, "output_tokens": 0})


_init_state()

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
        _init_state()
        st.success(tr("Wizard wurde zurückgesetzt.", "Wizard has been reset."))

render_salary_dashboard(st.session_state)

# --- Wizard einbinden als einzelne Page via st.navigation (verhindert pages/-Konflikte) ---
from wizard import run_wizard  # unsere neue Wizard-Funktion (siehe unten)  # noqa: E402

wizard_page = st.Page(run_wizard, title="Wizard", icon=":material/auto_awesome:")

# Optional: später weitere Pages (z. B. „About“) hinzufügen:
# about_page = st.Page(about.run, title="About", icon=":material/info:")

pg = st.navigation([wizard_page])  # Sidebar/Topbar Navigation (nur 1 Page)
pg.run()
