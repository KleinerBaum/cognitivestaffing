"""UI layout helpers extracted from ``wizard.py``."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Callable, Optional, Sequence, TypeVar, cast

import streamlit as st

from utils.i18n import tr

from ._logic import get_value, normalize_text_area_list, resolve_display_value


_SALARY_SLIDER_STYLE_KEY = "ui.salary.slider_style_injected"

T = TypeVar("T")


UpdateProfileFn = Callable[[str, Any], None]


@lru_cache(maxsize=1)
def _legacy_update_profile() -> UpdateProfileFn:
    """Return the historic ``_update_profile`` helper lazily."""

    module = import_module("wizard")
    update = getattr(module, "_update_profile", None)
    if not callable(update):  # pragma: no cover - defensive guard
        raise AttributeError("wizard._update_profile is not available")
    return cast(UpdateProfileFn, update)


def _ensure_widget_state(key: str, value: Any) -> None:
    """Seed ``st.session_state`` with ``value`` when ``key`` is missing."""

    if key not in st.session_state:
        st.session_state[key] = value


def _normalize_session_value(value: Any) -> Any:
    """Convert session state payloads to serialisable structures."""

    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return value


def _build_on_change(path: str, key: str) -> Callable[[], None]:
    """Return a callback that writes the widget value back to the profile."""

    def _callback() -> None:
        value = _normalize_session_value(st.session_state.get(key))
        _legacy_update_profile()(path, value)

    return _callback


def profile_text_input(
    path: str,
    label: str,
    *,
    placeholder: str | None = None,
    key: str | None = None,
    default: Any | None = None,
    value_formatter: Callable[[Any | None], str] | None = None,
    widget_factory: Callable[..., str] | None = None,
    **kwargs: Any,
) -> str:
    """Render a text input bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_text_input manages on_change internally")
    if "value" in kwargs:
        raise ValueError("profile_text_input derives value from the profile")

    widget_key = key or path
    display_value = resolve_display_value(path, default=default, formatter=value_formatter)
    _ensure_widget_state(widget_key, display_value)

    factory = widget_factory or st.text_input
    call_kwargs = dict(kwargs)
    if placeholder is not None:
        call_kwargs.setdefault("placeholder", placeholder)

    return factory(
        label,
        value=display_value,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **call_kwargs,
    )


def profile_selectbox(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: T | None = None,
    widget_factory: Callable[..., T] | None = None,
    **kwargs: Any,
) -> T:
    """Render a selectbox bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_selectbox manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    if not option_list:
        raise ValueError("profile_selectbox requires at least one option")

    requested_index = kwargs.pop("index", None)
    current = get_value(path)
    resolved_index: int
    if current in option_list:
        resolved_index = option_list.index(cast(T, current))
    elif default in option_list:
        resolved_index = option_list.index(cast(T, default))
    elif requested_index is not None:
        resolved_index = requested_index
    else:
        resolved_index = 0

    if not 0 <= resolved_index < len(option_list):
        raise IndexError("Resolved selectbox index out of range")

    default_value = option_list[resolved_index]
    _ensure_widget_state(widget_key, default_value)

    factory = widget_factory or st.selectbox
    return factory(
        label,
        option_list,
        index=resolved_index,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **kwargs,
    )


def profile_multiselect(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: Sequence[T] | None = None,
    widget_factory: Callable[..., Sequence[T]] | None = None,
    **kwargs: Any,
) -> list[T]:
    """Render a multiselect bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_multiselect manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    provided_default = kwargs.pop("default", None)

    current = get_value(path)
    if provided_default is not None:
        default_selection = list(provided_default)
    elif default is not None:
        default_selection = list(default)
    elif isinstance(current, (list, tuple, set, frozenset)):
        default_selection = [item for item in current if not option_list or item in option_list]
    elif current is None:
        default_selection = []
    else:
        default_selection = [current] if not option_list or current in option_list else []

    _ensure_widget_state(widget_key, list(default_selection))

    factory = widget_factory or st.multiselect
    return list(
        factory(
            label,
            option_list,
            default=default_selection,
            key=widget_key,
            on_change=_build_on_change(path, widget_key),
            **kwargs,
        )
    )


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
    if st.session_state.get(seed_key) != text_value:
        st.session_state[seed_key] = text_value
        if session_key in st.session_state:
            st.session_state[session_key] = text_value

    widget_args: dict[str, object] = {
        "label": label,
        "key": session_key,
        "height": height,
    }
    if placeholder:
        widget_args["placeholder"] = placeholder
    if session_key not in st.session_state:
        widget_args["value"] = text_value

    raw_value = st.text_area(**widget_args)
    cleaned_items = normalize_text_area_list(raw_value, strip_bullets=strip_bullets)
    st.session_state[seed_key] = "\n".join(cleaned_items)

    if required and not cleaned_items and on_required is not None:
        on_required(True)

    return cleaned_items


__all__ = [
    "COMPACT_STEP_STYLE",
    "profile_text_input",
    "profile_selectbox",
    "profile_multiselect",
    "render_list_text_area",
    "inject_salary_slider_styles",
    "render_onboarding_hero",
    "render_step_heading",
]
