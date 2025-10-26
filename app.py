# app.py — Cognitive Needs (clean entrypoint, single source of truth)
from __future__ import annotations

from base64 import b64encode
from io import BytesIO
from pathlib import Path
import sys
from typing import cast

from PIL import Image, ImageEnhance
import streamlit as st
from streamlit.navigation.page import StreamlitPage

APP_ROOT = Path(__file__).resolve().parent
for candidate in (APP_ROOT, APP_ROOT.parent):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

# Sidebar + favicon visuals use the former onboarding animation asset
APP_LOGO_PATH = APP_ROOT / "images" / "animation_pulse_Default_7kigl22lw.gif"
try:
    APP_LOGO_BYTES: bytes | None = APP_LOGO_PATH.read_bytes()
except FileNotFoundError:
    APP_LOGO_BYTES = None

from utils.telemetry import setup_tracing  # noqa: E402
from utils.i18n import tr  # noqa: E402
from state import ensure_state  # noqa: E402
from sidebar import SidebarPlan, render_sidebar  # noqa: E402
from wizard import run_wizard  # noqa: E402
from ui_views import advantages, gap_analysis  # noqa: E402

setup_tracing()

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool",
    page_icon=APP_LOGO_BYTES or "🧭",
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


def _load_background_image(dark_mode: bool) -> str | None:
    """Return the base64 encoded background image, adjusting for the theme."""

    bg_path = ROOT / "images" / "AdobeStock_506577005.jpeg"
    try:
        with Image.open(bg_path) as image:
            processed_image = image.convert("RGB")
            if not dark_mode:
                brightness = ImageEnhance.Brightness(processed_image)
                processed_image = brightness.enhance(0.55)

            buffer = BytesIO()
            processed_image.save(buffer, format="JPEG", quality=90)
    except FileNotFoundError:
        return None

    return b64encode(buffer.getvalue()).decode()


def inject_global_css() -> None:
    """Inject the global stylesheet and background image."""

    dark_mode = st.session_state.get("dark_mode", True)
    theme = "cognitive_needs.css" if dark_mode else "cognitive_needs_light.css"
    css = (ROOT / "styles" / theme).read_text(encoding="utf-8")
    encoded_bg = _load_background_image(dark_mode)
    bg_style = f":root {{ --bg-image: url('data:image/jpeg;base64,{encoded_bg}'); }}" if encoded_bg else ""
    st.markdown(
        f"<style>{css}\n{bg_style}</style>",
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
    background: linear-gradient(135deg, var(--surface-0), var(--surface-accent-secondary));
    border: 1px solid var(--border-subtle);
    box-shadow: var(--shadow-medium);
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
    opacity: 0.85;
}
.sidebar-hero * {
    color: var(--text-strong) !important;
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
    color: var(--text-soft);
}
.sidebar-step--current .sidebar-step__label {
    color: var(--accent);
}
.sidebar-step--warning .sidebar-step__note,
.sidebar-step--blocked .sidebar-step__note {
    color: rgba(214, 90, 78, 0.9);
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

wizard_page = st.Page(
    run_wizard,
    title=tr("Assistent", "Wizard"),
    icon=":material/auto_awesome:",
    url_path="wizard",
    default=True,
)
gap_analysis_page = st.Page(
    gap_analysis.run,
    title=tr("Gap-Analyse", "Gap analysis"),
    icon="🧠",
    url_path="gap-analysis",
)
advantages_page = st.Page(
    advantages.run,
    title=tr("Vorteile", "Advantages"),
    icon="💡",
    url_path="advantages",
)

sidebar_plan = render_sidebar(
    logo_bytes=APP_LOGO_BYTES,
    pages=[wizard_page, gap_analysis_page, advantages_page],
    defer=True,
)

if isinstance(sidebar_plan, SidebarPlan):
    selected_page: StreamlitPage | None = sidebar_plan.page
elif hasattr(sidebar_plan, "run"):
    selected_page = cast(StreamlitPage, sidebar_plan)
else:
    selected_page = None

if selected_page is not None:
    selected_page.run()
else:
    run_wizard()

if isinstance(sidebar_plan, SidebarPlan):
    render_sidebar(
        logo_bytes=APP_LOGO_BYTES,
        plan=sidebar_plan,
    )
