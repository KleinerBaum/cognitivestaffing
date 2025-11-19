"""UI layout helpers extracted from ``wizard.py``."""

from __future__ import annotations

import hashlib
import html
from base64 import b64encode
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal, Optional, Sequence

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from constants.keys import StateKeys
from utils.i18n import tr


LocalizedText = tuple[str, str]


class NavigationDirection(str, Enum):
    """Direction metadata for wizard navigation controls."""

    PREVIOUS = "previous"
    NEXT = "next"
    SKIP = "skip"


@dataclass(frozen=True)
class NavigationButtonState:
    """Typed configuration for a single navigation button."""

    direction: NavigationDirection
    label: LocalizedText
    target_key: str | None = None
    enabled: bool = True
    primary: bool = False
    hint: LocalizedText | None = None
    on_click: Callable[[], None] | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class NavigationState:
    """Aggregated state used to render navigation controls."""

    current_key: str
    missing_fields: tuple[str, ...] = ()
    previous: NavigationButtonState | None = None
    next: NavigationButtonState | None = None
    skip: NavigationButtonState | None = None


from ._logic import (
    _record_autofill_rejection,
    _update_profile,
    normalize_text_area_list,
)
from ._widget_state import _ensure_widget_state


_SALARY_SLIDER_STYLE_KEY = "ui.salary.slider_style_injected"


def _render_autofill_suggestion(
    *,
    field_path: str,
    suggestion: str,
    title: str,
    description: str,
    icon: str = "✨",
    success_message: str | None = None,
    rejection_message: str | None = None,
    success_icon: str = "✅",
    rejection_icon: str = "🗑️",
) -> None:
    """Render an optional autofill prompt for ``suggestion``."""

    cleaned_suggestion = suggestion.strip()
    if not cleaned_suggestion:
        return

    accept_label = f"{icon} {cleaned_suggestion}" if icon else cleaned_suggestion
    reject_label = tr("Ignorieren", "Dismiss")
    success_message = success_message or tr("Vorschlag übernommen.", "Suggestion applied.")
    rejection_message = rejection_message or tr("Vorschlag verworfen.", "Suggestion dismissed.")

    suggestion_hash = hashlib.sha1(f"{field_path}:{cleaned_suggestion}".encode("utf-8")).hexdigest()[:10]

    with st.container(border=True):
        st.markdown(f"**{title}**")
        if description:
            st.caption(description)
        st.markdown(f"`{cleaned_suggestion}`")
        accept_col, reject_col = st.columns((1.4, 1))
        if accept_col.button(
            accept_label,
            key=f"autofill.accept.{field_path}.{suggestion_hash}",
            type="primary",
        ):
            _update_profile(field_path, cleaned_suggestion)
            st.toast(success_message, icon=success_icon)
            st.rerun()
        if reject_col.button(
            reject_label,
            key=f"autofill.reject.{field_path}.{suggestion_hash}",
        ):
            _record_autofill_rejection(field_path, cleaned_suggestion)
            st.toast(rejection_message, icon=rejection_icon)
            st.rerun()


def render_navigation_controls(state: NavigationState) -> None:
    """Render the navigation controls based on ``state``."""

    st.markdown("<div class='wizard-nav-marker'></div>", unsafe_allow_html=True)
    cols = st.columns((1.1, 1.1, 1), gap="small")
    _render_navigation_button(cols[0], state.previous, state)
    _render_navigation_button(cols[1], state.next, state)
    _render_navigation_button(cols[2], state.skip, state)


def _render_navigation_button(
    column: DeltaGenerator,
    button: NavigationButtonState | None,
    state: NavigationState,
) -> None:
    if button is None:
        column.write("")
        return

    label = tr(*button.label)
    key = f"wizard_{button.direction.value}_{state.current_key}"
    button_type: Literal["primary", "secondary"] = "primary" if button.primary else "secondary"
    wrapper_open = False
    if button.direction is NavigationDirection.NEXT:
        modifier = "enabled" if button.enabled else "disabled"
        column.markdown(
            f"<div class='wizard-nav-next wizard-nav-next--{modifier}'>",
            unsafe_allow_html=True,
        )
        wrapper_open = True

    triggered = column.button(
        label,
        key=key,
        type=button_type,
        disabled=not button.enabled,
        use_container_width=True,
    )

    if wrapper_open:
        column.markdown("</div>", unsafe_allow_html=True)

    if triggered and button.on_click is not None:
        button.on_click()

    if button.hint:
        column.caption(tr(*button.hint))


COMPACT_STEP_STYLE = """
<style>
section.main div.block-container div[data-testid="stVerticalBlock"] {
    gap: var(--space-sm, 0.5rem) !important;
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
    margin-bottom: var(--space-xs, 0.4rem);
}
section.main div.block-container h1,
section.main div.block-container h2,
section.main div.block-container h3,
section.main div.block-container h4,
section.main div.block-container h5,
section.main div.block-container h6 {
    margin-top: var(--space-md, 0.75rem);
    margin-bottom: var(--space-xs, 0.35rem);
}
section.main div.block-container h1:first-child {
    margin-top: 0;
}
section.main div.block-container h2 {
    color: var(--text-strong);
}
section.main div.block-container h3,
section.main div.block-container h4,
section.main div.block-container h5 {
    color: var(--text-muted);
    font-weight: 600;
}
section.main div.block-container hr {
    margin-top: var(--space-md, 0.75rem);
    margin-bottom: var(--space-md, 0.75rem);
}
section.main div.block-container [data-testid="stMarkdownContainer"] p {
    margin-top: 0;
    margin-bottom: var(--space-xs, 0.35rem);
    line-height: 1.6;
    color: var(--text-soft);
}
section.main div.block-container [data-testid="stMarkdownContainer"] p strong {
    color: var(--text-strong);
}
section.main div.block-container [data-testid="stMarkdownContainer"] p em {
    color: var(--text-muted);
}
section.main div.block-container [data-testid="stMarkdownContainer"] ul,
section.main div.block-container [data-testid="stMarkdownContainer"] ol {
    margin-top: 0;
    margin-bottom: var(--space-xs, 0.35rem);
    padding-left: 1.1rem;
}
section.main div.block-container [data-testid="stMarkdownContainer"] li {
    margin-bottom: var(--space-2xs, 0.25rem);
}
section.main div.block-container label {
    display: inline-flex;
    gap: 0.35rem;
    align-items: center;
    font-size: 0.92rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--text-muted);
    transition: color var(--transition-base, 0.18s ease-out);
}
section.main div.block-container div[data-testid="stTextInput"] input,
section.main div.block-container div[data-testid="stTextArea"] textarea,
section.main div.block-container div[data-testid="stSelectbox"] select,
section.main div.block-container div[data-testid="stNumberInput"] input,
section.main div.block-container div[data-testid="stDateInput"] input,
section.main div.block-container div[data-testid="stMultiSelect"] input,
section.main div.block-container div[data-testid="stSlider"] input[type="range"] {
    border-radius: 14px;
    transition:
        border-color var(--transition-base, 0.18s ease-out),
        box-shadow var(--transition-base, 0.18s ease-out),
        background-color var(--transition-base, 0.18s ease-out);
    box-shadow: 0 0 0 0 transparent;
}
section.main div.block-container div[data-testid="stTextInput"] input:focus-visible,
section.main div.block-container div[data-testid="stTextArea"] textarea:focus-visible,
section.main div.block-container div[data-testid="stSelectbox"] select:focus-visible,
section.main div.block-container div[data-testid="stNumberInput"] input:focus-visible,
section.main div.block-container div[data-testid="stDateInput"] input:focus-visible,
section.main div.block-container div[data-testid="stMultiSelect"] input:focus-visible,
section.main div.block-container div[data-testid="stSlider"] input[type="range"]:focus-visible {
    border-color: var(--focus-ring-contrast, rgba(15, 23, 42, 0.35));
    box-shadow: 0 0 0 1px var(--focus-ring-contrast, rgba(15, 23, 42, 0.35)),
        0 0 0 4px var(--focus-ring, rgba(59, 130, 246, 0.35));
}
section.main div.block-container div[data-testid="stButton"] button,
section.main div.block-container div[data-testid="stDownloadButton"] button,
section.main div.block-container div[data-testid="stFormSubmitButton"] button {
    transition:
        transform var(--transition-base, 0.18s ease-out),
        box-shadow var(--transition-base, 0.18s ease-out),
        background-color var(--transition-base, 0.18s ease-out);
    will-change: transform, box-shadow;
}
section.main div.block-container div[data-testid="stButton"] button:hover:not(:disabled),
section.main div.block-container div[data-testid="stDownloadButton"] button:hover:not(:disabled),
section.main div.block-container div[data-testid="stFormSubmitButton"] button:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 18px rgba(15, 23, 42, 0.16);
}
section.main div.block-container div[data-testid="stButton"] button:active:not(:disabled),
section.main div.block-container div[data-testid="stDownloadButton"] button:active:not(:disabled),
section.main div.block-container div[data-testid="stFormSubmitButton"] button:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 8px 14px rgba(15, 23, 42, 0.14);
}
section.main div.block-container div[data-testid="stCaptionContainer"] {
    margin-top: calc(var(--space-2xs, 0.25rem) * -0.5);
}
section.main div.block-container div[data-testid="stCaptionContainer"] p {
    margin: 0;
    color: var(--text-soft);
}
section.main div.block-container div[data-testid="stRadio"] label,
section.main div.block-container div[data-testid="stCheckbox"] > label {
    padding: 0.4rem 0.6rem;
    border-radius: 12px;
    transition: background 0.15s ease, box-shadow 0.15s ease, color 0.15s ease;
}
section.main div.block-container div[data-testid="stRadio"] label:hover,
section.main div.block-container div[data-testid="stCheckbox"] > label:hover {
    background: var(--surface-hover);
}
section.main div.block-container div[data-testid="stRadio"] label:focus-within,
section.main div.block-container div[data-testid="stCheckbox"] > label:focus-within {
    background: var(--surface-press);
    box-shadow: 0 0 0 2px var(--focus-ring-contrast), 0 0 0 6px var(--focus-ring);
}
section.main div.block-container div[data-testid="stSlider"] .stSliderTickBar {
    color: var(--text-soft);
}
section.main div.block-container div[data-testid="column"] {
    padding-left: var(--space-2xs, 0.25rem) !important;
    padding-right: var(--space-2xs, 0.25rem) !important;
}
section.main div.block-container div[data-testid="stHorizontalBlock"] {
    gap: var(--space-sm, 0.5rem) !important;
}
section.main div.block-container .stTabs [data-baseweb="tab-list"] {
    gap: var(--space-xs, 0.35rem) !important;
    padding: var(--space-2xs, 0.25rem);
}
section.main div.block-container .stTabs [data-baseweb="tab"] {
    padding-top: var(--space-2xs, 0.3rem);
    padding-bottom: var(--space-2xs, 0.3rem);
}

@media (max-width: 768px) {
    section.main div.block-container div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        align-items: stretch !important;
    }

    section.main div.block-container div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    section.main div.block-container div[data-testid="stButton"] button,
    section.main div.block-container div[data-testid="stFormSubmitButton"] button,
    section.main div.block-container div[data-testid="stDownloadButton"] button {
        width: 100%;
    }
}

@media (max-width: 640px) {
    section.main div.block-container h1 {
        font-size: clamp(1.6rem, 1.3rem + 1.2vw, 2.1rem);
    }
    section.main div.block-container h2 {
        font-size: clamp(1.35rem, 1.1rem + 0.8vw, 1.7rem);
    }
}
</style>
"""

_SECTION_HEADING_STYLE_KEY = "ui.section_heading_styles_v1"

SECTION_HEADING_STYLE = """
<style>
.wizard-section-heading {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 1.25rem 0 0.65rem;
    font-size: 1.08rem;
    font-weight: 660;
    letter-spacing: -0.01em;
    color: var(--text-strong, #0f172a);
}
.wizard-section-heading:first-child {
    margin-top: 0.35rem;
}
.wizard-section-heading__icon {
    font-size: 1.05em;
    line-height: 1;
}
.wizard-section-heading__eyebrow {
    display: inline-flex;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted, #475569);
}
.wizard-section-heading--compact {
    font-size: 0.98rem;
    font-weight: 640;
    margin-top: 1rem;
    margin-bottom: 0.45rem;
}
.wizard-section-heading--micro {
    font-size: 0.9rem;
    font-weight: 620;
    margin-top: 0.9rem;
    margin-bottom: 0.35rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted, #475569);
}
</style>
"""


def _ensure_section_heading_styles() -> None:
    """Inject shared styles for section headings once per session."""

    if st.session_state.get(_SECTION_HEADING_STYLE_KEY):
        return
    st.session_state[_SECTION_HEADING_STYLE_KEY] = True
    st.markdown(SECTION_HEADING_STYLE, unsafe_allow_html=True)


def render_section_heading(
    label: str,
    *,
    icon: str | None = None,
    eyebrow: str | None = None,
    size: Literal["default", "compact", "micro"] = "default",
    target: DeltaGenerator | None = None,
    description: str | None = None,
) -> None:
    """Render a consistent heading element for subsections within a step."""

    _ensure_section_heading_styles()
    normalized_size = size if size in {"default", "compact", "micro"} else "default"
    classes = ["wizard-section-heading"]
    if normalized_size != "default":
        classes.append(f"wizard-section-heading--{normalized_size}")

    icon_html = f"<span class='wizard-section-heading__icon'>{html.escape(icon)}</span>" if icon else ""
    eyebrow_html = f"<span class='wizard-section-heading__eyebrow'>{html.escape(eyebrow)}</span>" if eyebrow else ""
    label_html = f"<span>{html.escape(label)}</span>"
    heading_html = f"<div class='{' '.join(classes)}'>{icon_html}{eyebrow_html}{label_html}</div>"
    destination = target or st
    destination.markdown(heading_html, unsafe_allow_html=True)
    if description:
        destination.caption(description)


ONBOARDING_HERO_STYLE = """
<style>
.onboarding-hero {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    gap: clamp(1rem, 3vw, 2.75rem);
    align-items: center;
    margin: 1.2rem 0 1.4rem;
    padding: clamp(1.4rem, 1rem + 2vw, 2.4rem);
    background: var(--hero-panel-bg);
    border: 1px solid var(--hero-panel-border);
    border-radius: clamp(1.2rem, 0.8rem + 1vw, 1.75rem);
    box-shadow: var(--shadow-medium);
    overflow: hidden;
}
.onboarding-hero::after {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--hero-overlay);
    pointer-events: none;
}
.onboarding-hero > * {
    position: relative;
    z-index: 1;
}
.onboarding-hero__logo {
    flex: 0 1 clamp(200px, 28vw, 320px);
    display: flex;
    justify-content: center;
}
.onboarding-hero__logo img {
    width: clamp(180px, 24vw, 320px);
    height: auto;
    filter: var(--hero-image-filter);
}
.onboarding-hero__copy {
    flex: 1 1 280px;
    max-width: var(--hero-copy-max-width, 640px);
}
.onboarding-hero__eyebrow {
    font-size: 0.8rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.5rem;
}
.onboarding-hero__headline {
    margin: 0;
    font-size: clamp(1.9rem, 1.2rem + 2vw, 2.6rem);
    font-weight: 700;
    line-height: 1.2;
    color: var(--text-strong);
}
.onboarding-hero__subheadline {
    margin-top: 0.85rem;
    font-size: clamp(1.05rem, 0.95rem + 0.45vw, 1.25rem);
    color: var(--text-muted);
    line-height: 1.6;
}
@media (max-width: 768px) {
    .onboarding-hero {
        justify-content: center;
        text-align: center;
    }
    .onboarding-hero__copy {
        flex-basis: 100%;
        max-width: 100%;
    }
}
@media (max-width: 540px) {
    .onboarding-hero {
        padding: clamp(1.1rem, 0.9rem + 1.2vw, 1.6rem);
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
            background: linear-gradient(
                90deg,
                var(--slider-track-start, var(--accent)),
                var(--slider-track-end, var(--accent-2))
            );
            box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18), 0 12px 24px rgba(15, 23, 42, 0.22);
            border-radius: 999px;
            transition: box-shadow 0.2s ease;
        }
        div[data-testid="stSlider"] .stSliderRail {
            background: var(--slider-rail, rgba(148, 163, 184, 0.25));
            border-radius: 999px;
        }
        div[data-testid="stSlider"] div[role="slider"] {
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: var(--slider-thumb-fill, var(--surface-contrast));
            border: 2px solid var(--slider-thumb-border, var(--accent));
            box-shadow: var(--slider-thumb-shadow, 0 0 0 3px rgba(30, 136, 247, 0.18));
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        div[data-testid="stSlider"] div[role="slider"]:hover {
            transform: scale(1.05);
        }
        div[data-testid="stSlider"] div[role="slider"]:focus-visible {
            outline: none;
            box-shadow: 0 0 0 2px var(--focus-ring-contrast), 0 0 0 6px var(--focus-ring);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_SALARY_SLIDER_STYLE_KEY] = True


def render_onboarding_hero(animation_bytes: bytes | None, *, mime_type: str = "image/gif") -> None:
    """Render the onboarding hero with logo and positioning copy."""

    if not animation_bytes:
        return

    st.markdown(ONBOARDING_HERO_STYLE, unsafe_allow_html=True)

    animation_base64 = b64encode(animation_bytes).decode("ascii")

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
            <img src="data:{mime_type};base64,{animation_base64}" alt="Cognitive Staffing logo" />
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


def _extract_warning_details(summary: Any, warning_text: str, lang: str | None) -> str | None:
    """Return a detail string for the current warning summary if available."""

    if isinstance(summary, str):
        candidate = summary.strip()
        if candidate and candidate != warning_text.strip():
            return candidate
        return None

    if not isinstance(summary, Mapping):
        return None

    localized_keys = [
        tr("Fehlerdetails", "Error details", lang=lang),
        tr("Betroffene Felder", "Impacted fields", lang=lang),
        tr("Details", "Details", lang=lang),
        "Fehlerdetails",
        "Error details",
        "Betroffene Felder",
        "Impacted fields",
        "Details",
    ]
    for key in localized_keys:
        if key not in summary:
            continue
        value = summary.get(key)
        if isinstance(value, str):
            candidate = value.strip()
            if candidate:
                return candidate
    return None


def render_step_warning_banner() -> None:
    """Display a bilingual warning banner when extraction repairs are active."""

    warning_text = st.session_state.get(StateKeys.STEPPER_WARNING)
    if not isinstance(warning_text, str) or not warning_text.strip():
        return

    lang = st.session_state.get("lang")
    summary = st.session_state.get(StateKeys.EXTRACTION_SUMMARY)
    detail_text = _extract_warning_details(summary, warning_text, lang)
    if detail_text:
        detail_label = tr("Details", "Details", lang=lang)
        message = f"{warning_text}\n\n{detail_label}:\n{detail_text}"
    else:
        message = warning_text
    st.warning(message)


def render_list_text_area(
    *,
    label: str,
    session_key: str,
    items: Sequence[str] | None = None,
    placeholder: str | None = None,
    height: int = 200,
    required: bool = False,
    on_required: Callable[[bool], None] | None = None,
    strip_bullets: bool = True,
) -> list[str]:
    """Render a multi-line text area bound to a list value."""

    current_items = [str(item).strip() for item in (items or []) if isinstance(item, str) and str(item).strip()]
    text_value = "\n".join(current_items)
    seed_key = f"{session_key}.__seed"
    seed_state = st.session_state.get(seed_key)
    if seed_state != text_value:
        _ensure_widget_state(seed_key, text_value)
        _ensure_widget_state(session_key, text_value)
    elif session_key not in st.session_state:
        _ensure_widget_state(session_key, text_value)

    widget_args: dict[str, Any] = {
        "label": label,
        "key": session_key,
        "height": height,
    }
    if placeholder:
        widget_args["placeholder"] = placeholder

    raw_value = st.text_area(**widget_args)
    cleaned_items = normalize_text_area_list(raw_value, strip_bullets=strip_bullets)
    updated_seed_value = "\n".join(cleaned_items)
    if st.session_state.get(seed_key) != updated_seed_value:
        _ensure_widget_state(seed_key, updated_seed_value)

    if required and not cleaned_items and on_required is not None:
        on_required(True)

    return cleaned_items


__all__ = [
    "COMPACT_STEP_STYLE",
    "NavigationButtonState",
    "NavigationDirection",
    "NavigationState",
    "render_list_text_area",
    "render_navigation_controls",
    "inject_salary_slider_styles",
    "render_onboarding_hero",
    "render_section_heading",
    "render_step_heading",
    "render_step_warning_banner",
]
