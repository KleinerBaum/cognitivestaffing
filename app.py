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
        sys.path.append(candidate_str)

from components.salary_dashboard import render_salary_dashboard  # noqa: E402
from components.model_selector import model_selector  # noqa: E402
from components.reasoning_selector import reasoning_selector  # noqa: E402
from constants.keys import UIKeys  # noqa: E402
from config_loader import load_json  # noqa: E402
from utils.i18n import tr  # noqa: E402
from state import ensure_state, reset_state  # noqa: E402

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

SIDEBAR_CONTAINER_SELECTOR = "section[data-testid='stSidebar']"
SIDEBAR_COLLAPSE_SELECTORS = (
    "div[data-testid='collapsedControl']",
    "div[data-testid='stSidebarCollapsedControl']",
)


def apply_sidebar_visibility(visible: bool) -> None:
    """Apply CSS rules to enforce the preferred sidebar visibility.

    Args:
        visible: Whether the sidebar should be shown.
    """

    hidden_selectors = list(SIDEBAR_COLLAPSE_SELECTORS)
    if not visible:
        hidden_selectors.append(SIDEBAR_CONTAINER_SELECTOR)
    css_rules = "\n".join(
        f"{selector} {{ display: none; }}" for selector in hidden_selectors
    )
    st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)


sidebar_visible = st.session_state.get(UIKeys.SIDEBAR_VISIBLE, True)
apply_sidebar_visibility(sidebar_visible)

toggle_placeholder = st.container()

if not sidebar_visible:
    with toggle_placeholder:
        _, button_col = st.columns([1, 0.22])
        with button_col:
            if st.button(
                tr("➡️ Sidebar einblenden", "➡️ Show sidebar"),
                key=UIKeys.SIDEBAR_SHOW,
            ):
                st.session_state[UIKeys.SIDEBAR_VISIBLE] = True
                st.rerun()

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

# --- Sidebar: globale Controls ---
if sidebar_visible:
    with st.sidebar:
        if st.button(
            tr("⬅️ Sidebar ausblenden", "⬅️ Hide sidebar"),
            key=UIKeys.SIDEBAR_HIDE,
            use_container_width=True,
        ):
            st.session_state[UIKeys.SIDEBAR_VISIBLE] = False
            st.rerun()

        st.markdown(tr("### ⚙️ Einstellungen", "### ⚙️ Settings"))
        st.session_state.lang = st.selectbox(
            tr("Sprache", "Language"),
            ["de", "en"],
            index=(0 if st.session_state.lang == "de" else 1),
        )
        if "ui.dark_mode" not in st.session_state:
            st.session_state["ui.dark_mode"] = st.session_state.get("dark_mode", True)

        def _on_theme_toggle() -> None:
            st.session_state["dark_mode"] = st.session_state["ui.dark_mode"]

        st.toggle("Dark Mode 🌙", key="ui.dark_mode", on_change=_on_theme_toggle)
        model_selector()
        reasoning_selector()

        if st.button("🔁 Reset Wizard", type="secondary"):
            reset_state()
            st.success(tr("Wizard wurde zurückgesetzt.", "Wizard has been reset."))

    render_salary_dashboard(st.session_state)

# --- Wizard einbinden + Advantages Page via st.navigation ---
from wizard import run_wizard  # noqa: E402
from pages import advantages  # noqa: E402

wizard_page = st.Page(run_wizard, title="Wizard", icon=":material/auto_awesome:")
advantages_page = st.Page(advantages.run, title="Advantages", icon="💡")

pg = st.navigation([wizard_page, advantages_page])
pg.run()
