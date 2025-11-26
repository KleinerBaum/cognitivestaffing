# app.py — Cognitive Needs (clean entrypoint, single source of truth)
from __future__ import annotations

from base64 import b64encode
from io import BytesIO
import mimetypes
from pathlib import Path
import sys
from typing import Final, cast

from PIL import Image, ImageEnhance, UnidentifiedImageError
import streamlit as st

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

APP_LOGO_BUFFER: BytesIO | None = None
APP_LOGO_IMAGE: Image.Image | None = None
APP_LOGO_DATA_URI: str | None = None

if APP_LOGO_BYTES:
    APP_LOGO_BUFFER = BytesIO(APP_LOGO_BYTES)
    setattr(APP_LOGO_BUFFER, "name", APP_LOGO_PATH.name)

    try:
        with Image.open(BytesIO(APP_LOGO_BYTES)) as loaded_logo:
            copied_logo = loaded_logo.copy()
        copied_logo.load()
        APP_LOGO_IMAGE = copied_logo
    except UnidentifiedImageError:
        APP_LOGO_IMAGE = None

    mime_type, _encoding = mimetypes.guess_type(APP_LOGO_PATH.name)
    safe_mime = mime_type or "image/png"
    APP_LOGO_DATA_URI = f"data:{safe_mime};base64,{b64encode(APP_LOGO_BYTES).decode('ascii')}"

from openai import OpenAI  # noqa: E402

from config import (  # noqa: E402
    LLM_ENABLED,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
)
from llm.model_router import pick_model  # noqa: E402
from utils.telemetry import setup_tracing  # noqa: E402
from utils.i18n import tr  # noqa: E402
from state import ensure_state  # noqa: E402
from state.autosave import maybe_render_autosave_prompt  # noqa: E402
from components.chatkit_widget import inject_chatkit_script  # noqa: E402
from sidebar import render_sidebar  # noqa: E402
from wizard import run_wizard  # noqa: E402

APP_VERSION = "1.1.0"
INTRO_BANNER_STATE_KEY: Final[str] = "ui.show_intro_banner"

setup_tracing()

# --- Page config early (keine doppelten Titel/Icon-Resets) ---
st.set_page_config(
    page_title="Cognitive Needs - AI powered Recruitment Analysis, Detection and Improvement Tool",
    page_icon=APP_LOGO_IMAGE or APP_LOGO_BUFFER or "🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helpers zum Laden lokaler JSON-Configs ---
ROOT = APP_ROOT
ensure_state()
st.session_state.setdefault("app_version", APP_VERSION)

MODEL_ID = cast(str | None, st.session_state.get("router.resolved_model"))
if LLM_ENABLED:
    if MODEL_ID is None:
        try:
            router_client = OpenAI(
                api_key=OPENAI_API_KEY or None,
                base_url=OPENAI_BASE_URL or None,
                organization=OPENAI_ORGANIZATION or None,
                project=OPENAI_PROJECT or None,
            )
            MODEL_ID = pick_model(router_client)
            st.session_state["router.resolved_model"] = MODEL_ID
            st.session_state["router.model_logged"] = True
            print(f"[MODEL_ROUTER_V3] using model={MODEL_ID}")
        except Exception as exc:  # pragma: no cover - defensive startup logging
            print(f"[MODEL_ROUTER_V3] unable to resolve model: {exc}")
    elif not st.session_state.get("router.model_logged"):
        print(f"[MODEL_ROUTER_V3] using model={MODEL_ID}")
        st.session_state["router.model_logged"] = True
else:
    print("[MODEL_ROUTER_V3] OpenAI API key not configured; model routing skipped.")

if MODEL_ID and "router.resolved_model" not in st.session_state:
    st.session_state["router.resolved_model"] = MODEL_ID

wizard_state = st.session_state.setdefault("wizard", {})

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

maybe_render_autosave_prompt()


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
inject_chatkit_script()


def _set_intro_banner_visibility(visible: bool) -> None:
    """Persist whether the intro banner should be shown on reruns."""

    st.session_state[INTRO_BANNER_STATE_KEY] = visible


def render_app_banner() -> None:
    """Render the global hero banner with logo and bilingual copy."""

    badge_entries = [
        tr("🧠 Geführter Wizard", "🧠 Guided wizard"),
        tr("📊 Markt- & Gehaltsanalysen", "📊 Market & salary insights"),
        tr("🧩 ESCO-Skill-Mapping", "🧩 ESCO skill mapping"),
    ]
    eyebrow = tr("Recruiting-Bedarfsanalyse", "Recruitment Need Analysis")
    headline = tr(
        "Cognitive Staffing – vollständiges Stellenprofil für deinen speziellen Bedarf",
        "Cognitive Staffing – Complete Jobspec for your special Need",
    )
    subtitle = tr(
        (
            "Individuelle und dynamische Fragestellungen sowie Marktbenchmarks "
            "helfen dir, Profile und Ergebnisse mit Sicherheit und Präzision zu verfeinern."
        ),
        (
            "Tailored and dynamic questioning as well as market benchmarks help you "
            "refine profiles and deliverables with confidence and precision"
        ),
    )

    if APP_LOGO_DATA_URI:
        logo_html = f"<img src='{APP_LOGO_DATA_URI}' alt='Cognitive Staffing logo' />"
    elif APP_LOGO_IMAGE:
        buffer = BytesIO()
        APP_LOGO_IMAGE.save(buffer, format="PNG")
        encoded = b64encode(buffer.getvalue()).decode("ascii")
        logo_html = f"<img src='data:image/png;base64,{encoded}' alt='Cognitive Staffing logo' />"
    elif APP_LOGO_BUFFER:
        encoded = b64encode(APP_LOGO_BUFFER.getvalue()).decode("ascii")
        mime_type, _ = mimetypes.guess_type(getattr(APP_LOGO_BUFFER, "name", "logo.png"))
        logo_html = f"<img src='data:{mime_type or 'image/png'};base64,{encoded}' alt='Cognitive Staffing logo' />"
    else:
        logo_html = "<span class='app-banner__logo-placeholder'>🧭</span>"

    badges_html = "".join(f"<span class='app-banner__meta-badge'>{html_badge}</span>" for html_badge in badge_entries)

    banner_html = f"""
    <div class="app-banner">
        <div class="app-banner__logo">{logo_html}</div>
        <div class="app-banner__copy">
            <div class="app-banner__eyebrow">{eyebrow}</div>
            <h1 class="app-banner__headline">{headline}</h1>
            <p class="app-banner__subtitle">{subtitle}</p>
            <div class="app-banner__meta">{badges_html}</div>
        </div>
    </div>
    """

    st.markdown(banner_html, unsafe_allow_html=True)


def render_intro_banner_controls(showing: bool) -> None:
    """Render a toggle to hide or show the intro banner."""

    if showing:
        hide_label = tr("Intro ausblenden", "Hide intro")
        hide_help = tr(
            "Blendet das Intro aus, damit mehr Platz für das Formular bleibt.",
            "Hide the intro to focus on the form.",
        )
        st.button(
            hide_label,
            key="hide_intro_banner",
            help=hide_help,
            on_click=lambda: _set_intro_banner_visibility(False),
        )
    else:
        show_label = tr("Intro einblenden", "Show intro")
        show_help = tr(
            "Zeigt das Intro wieder an, falls es ausgeblendet wurde.",
            "Show the intro banner again if it was hidden.",
        )
        st.button(
            show_label,
            key="show_intro_banner",
            help=show_help,
            on_click=lambda: _set_intro_banner_visibility(True),
        )


intro_banner_visible = st.session_state.setdefault(INTRO_BANNER_STATE_KEY, True)

if intro_banner_visible:
    render_app_banner()

render_intro_banner_controls(intro_banner_visible)

SIDEBAR_STYLE = """
<style>
[data-testid="stSidebar"] .block-container {
    padding-top: var(--space-lg);
}
.sidebar-hero {
    display: flex;
    gap: var(--space-md);
    align-items: center;
    padding: var(--space-lg);
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--surface-0), var(--surface-accent-secondary));
    border: 1px solid var(--border-subtle);
    box-shadow: var(--shadow-medium);
    margin-bottom: var(--space-lg);
    transition: box-shadow var(--transition-base), background var(--transition-base);
}
.sidebar-hero__visual {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: calc(var(--space-lg) * 3.5);
    height: calc(var(--space-lg) * 3.5);
    border-radius: var(--radius-sm);
    background: var(--surface-accent-soft);
    border: 1px solid var(--border-subtle);
    overflow: hidden;
}
.sidebar-hero__logo {
    max-width: calc(var(--space-lg) * 3.5);
    max-height: calc(var(--space-lg) * 3.5);
    object-fit: contain;
}
.sidebar-hero__avatar {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: calc(var(--space-lg) * 3.5);
    height: calc(var(--space-lg) * 3.5);
    border-radius: var(--radius-md);
    font-weight: 700;
    font-size: calc(var(--space-lg) * 1.4);
    background: var(--surface-accent-strong);
    color: var(--text-on-accent);
}
.sidebar-hero__icon {
    font-size: calc(var(--space-lg) * 2.4);
}
.sidebar-hero__eyebrow {
    text-transform: uppercase;
    font-size: calc(var(--space-lg) - var(--space-sm) / 2);
    letter-spacing: 0.22em;
    opacity: 0.8;
    margin: 0 0 calc(var(--space-sm) / 2) 0;
}
.sidebar-hero__title {
    margin: 0;
    font-size: calc(var(--space-lg) + var(--space-sm) / 2);
    font-weight: 700;
}
.sidebar-hero__subtitle {
    margin: calc(var(--space-sm) / 2) 0 0;
    font-size: calc(var(--space-lg) - var(--space-sm) / 4);
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
    gap: calc(var(--space-sm) * 0.9);
    padding: calc(var(--space-sm) / 2) 0;
    font-size: calc(var(--space-lg) - var(--space-sm) / 5);
    transition: color var(--transition-base);
}
.sidebar-step__badge {
    width: calc(var(--space-lg) * 1.6);
    display: inline-flex;
    justify-content: center;
}
.sidebar-step__label {
    font-weight: 600;
}
.sidebar-step__note {
    margin-left: auto;
    font-size: var(--space-md);
    color: var(--text-soft);
}
.sidebar-step--current .sidebar-step__label {
    color: var(--accent-strong);
}
.sidebar-step--warning .sidebar-step__note,
.sidebar-step--blocked .sidebar-step__note {
    color: rgba(214, 90, 78, 0.9);
}
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 {
    margin-top: var(--space-md);
    margin-bottom: var(--space-sm);
}
[data-testid="stSidebar"] h4 {
    font-size: var(--space-lg);
}
[data-testid="stSidebar"] .stMarkdown ul {
    margin-bottom: var(--space-sm);
}

@media (max-width: 768px) {
    [data-testid="stSidebar"] .block-container {
        padding-top: var(--space-md);
    }
    .sidebar-hero {
        flex-direction: column;
        align-items: flex-start;
    }
    .sidebar-hero__visual {
        width: calc(var(--space-lg) * 3);
        height: calc(var(--space-lg) * 3);
    }
    .sidebar-hero__logo {
        max-width: calc(var(--space-lg) * 3);
        max-height: calc(var(--space-lg) * 3);
    }
}
</style>
"""

st.markdown(SIDEBAR_STYLE, unsafe_allow_html=True)

sidebar_plan = render_sidebar(
    logo_asset=APP_LOGO_IMAGE or APP_LOGO_BUFFER,
    logo_data_uri=APP_LOGO_DATA_URI,
    defer=True,
)

run_wizard()

render_sidebar(
    logo_asset=APP_LOGO_IMAGE or APP_LOGO_BUFFER,
    logo_data_uri=APP_LOGO_DATA_URI,
    plan=sidebar_plan,
)
