"""UI layout helpers extracted from ``wizard.py``."""

from __future__ import annotations

import streamlit as st

from typing import Optional

from utils.i18n import tr


_SALARY_SLIDER_STYLE_KEY = "ui.salary.slider_style_injected"

COMPACT_STEP_STYLE = """
<style>
section.main div.block-container div[data-testid="stVerticalBlock"] {
    gap: 0.35rem !important;
}
section.main div.block-container div[data-testid="stTextInput"],
section.main div.block-container div[data-testid="stTextArea"],
section.main div.block-container div[data-testid="stSelectbox"],
section.main div.block-container div[data-testid="stMultiSelect"],
section.main div.block-container div[data-testid="stNumberInput"],
section.main div.block-container div[data-testid="stCheckbox"],
section.main div.block-container div[data-testid="stRadio"],
section.main div.block-container div[data-testid="stSlider"],
section.main div.block-container div[data-testid="stDateInput"],
section.main div.block-container div[data-testid="stDownloadButton"],
section.main div.block-container div[data-testid="stButton"],
section.main div.block-container div[data-testid="stFormSubmitButton"],
section.main div.block-container div[data-testid="stFileUploader"],
section.main div.block-container div[data-testid="stCaptionContainer"],
section.main div.block-container div[data-testid="stMarkdownContainer"] {
    margin-bottom: 0.35rem;
}
section.main div.block-container h1,
section.main div.block-container h2,
section.main div.block-container h3,
section.main div.block-container h4,
section.main div.block-container h5,
section.main div.block-container h6 {
    margin-top: 0.75rem;
    margin-bottom: 0.35rem;
}
section.main div.block-container hr {
    margin-top: 0.75rem;
    margin-bottom: 0.75rem;
}
section.main div.block-container div[data-testid="column"] {
    padding-left: 0.25rem !important;
    padding-right: 0.25rem !important;
}
section.main div.block-container div[data-testid="stHorizontalBlock"] {
    gap: 0.5rem !important;
}
section.main div.block-container .stTabs [data-baseweb="tab-list"] {
    gap: 0.35rem !important;
}
section.main div.block-container .stTabs [data-baseweb="tab"] {
    padding-top: 0.35rem;
    padding-bottom: 0.35rem;
}
</style>
"""

ONBOARDING_HERO_STYLE = """
<style>
.onboarding-hero {
    display: flex;
    flex-wrap: wrap;
    gap: clamp(1rem, 3vw, 2.75rem);
    align-items: center;
    margin: 1.2rem 0 1.4rem;
}
.onboarding-hero__logo {
    flex: 0 1 clamp(200px, 28vw, 320px);
    display: flex;
    justify-content: center;
}
.onboarding-hero__logo img {
    width: clamp(180px, 24vw, 320px);
    height: auto;
    filter: drop-shadow(0 18px 36px rgba(8, 10, 10, 0.45));
}
.onboarding-hero__copy {
    flex: 1 1 280px;
}
.onboarding-hero__eyebrow {
    font-size: 0.8rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.45rem;
}
.onboarding-hero__headline {
    margin: 0;
    font-size: clamp(1.9rem, 1.2rem + 2vw, 2.6rem);
    font-weight: 700;
    color: var(--text-strong);
}
.onboarding-hero__subheadline {
    margin-top: 0.75rem;
    font-size: clamp(1.05rem, 0.95rem + 0.45vw, 1.25rem);
    color: var(--text-muted);
    line-height: 1.55;
}
@media (max-width: 768px) {
    .onboarding-hero {
        justify-content: center;
        text-align: center;
    }
    .onboarding-hero__copy {
        flex-basis: 100%;
    }
}
</style>
"""


def inject_salary_slider_styles() -> None:
    """Inject custom styling for the salary slider once per session."""

    if st.session_state.get(_SALARY_SLIDER_STYLE_KEY):
        return
    st.markdown(
        """
        <style>
        div[data-testid="stSlider"] .stSliderTrack {
            background: linear-gradient(90deg, #1f6feb, #7f00ff);
            box-shadow: 0 0 12px rgba(31, 111, 235, 0.45);
        }
        div[data-testid="stSlider"] div[role="slider"] {
            background: radial-gradient(circle at 30% 30%, #ffffff, #00f0ff);
            border: 2px solid rgba(127, 0, 255, 0.75);
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.55);
        }
        div[data-testid="stSlider"] .stSliderRail {
            background: linear-gradient(90deg, rgba(31, 111, 235, 0.25), rgba(127, 0, 255, 0.25));
            border-radius: 999px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_SALARY_SLIDER_STYLE_KEY] = True


def render_onboarding_hero(animation_base64: str) -> None:
    """Render the onboarding hero with logo and positioning copy."""

    if not animation_base64:
        return

    st.markdown(ONBOARDING_HERO_STYLE, unsafe_allow_html=True)

    hero_eyebrow = tr("Recruiting Intelligence", "Recruiting intelligence")
    hero_title = tr(
        "Dynamische Recruiting-Analysen zur Identifikation & Nutzung **aller** vakanzspezifischen Informationen",
        "Cognitive Staffing – precise recruiting analysis in minutes",
    )
    hero_subtitle = tr(
        (
            "Verbinde strukturierte Extraktion, KI-Validierung und Marktbenchmarks, "
            "um jede Stellenanzeige verlässlich zu bewerten und gezielt zu optimieren."
        ),
        (
            "Combine structured extraction, AI validation, and market benchmarks to "
            "review every job ad with confidence and improve it with purpose."
        ),
    )

    hero_html = f"""
    <div class="onboarding-hero">
        <div class="onboarding-hero__logo">
            <img src="data:image/png;base64,{animation_base64}" alt="Cognitive Staffing logo" />
        </div>
        <div class="onboarding-hero__copy">
            <div class="onboarding-hero__eyebrow">{hero_eyebrow}</div>
            <h1 class="onboarding-hero__headline">{hero_title}</h1>
            <p class="onboarding-hero__subheadline">{hero_subtitle}</p>
        </div>
    </div>
    """

    st.markdown(hero_html, unsafe_allow_html=True)


def render_step_heading(title: str, subtitle: Optional[str] = None) -> None:
    """Render a consistent heading block for wizard steps."""

    st.header(title)
    if subtitle:
        st.subheader(subtitle)


__all__ = [
    "COMPACT_STEP_STYLE",
    "inject_salary_slider_styles",
    "render_onboarding_hero",
    "render_step_heading",
]
