"""UI layout helpers extracted from ``wizard.py``."""

from __future__ import annotations

import hashlib
import html
from base64 import b64encode
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Collection, Final, Iterable, Literal, Optional, Sequence

from datetime import datetime

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from constants.keys import ProfilePaths, StateKeys
from wizard.sections.followups import CRITICAL_FIELD_PROMPTS
from utils.i18n import tr


LocalizedText = tuple[str, str]

_REQUIRED_FIELD_LABELS: Final[dict[str, tuple[str, str]]] = {
    str(ProfilePaths.COMPANY_NAME): ("Unternehmensname", "Company name"),
    str(ProfilePaths.COMPANY_CONTACT_EMAIL): ("Kontakt-E-Mail", "Contact email"),
    str(ProfilePaths.COMPANY_CONTACT_PHONE): ("Kontakt-Telefon", "Contact phone"),
    str(ProfilePaths.LOCATION_PRIMARY_CITY): ("Primäre Stadt", "Primary city"),
    str(ProfilePaths.LOCATION_COUNTRY): ("Land", "Country"),
    str(ProfilePaths.DEPARTMENT_NAME): ("Abteilung", "Department"),
    str(ProfilePaths.TEAM_REPORTING_LINE): ("Berichtslinie", "Reporting line"),
    str(ProfilePaths.POSITION_REPORTING_MANAGER_NAME): (
        "Vorgesetzte Person",
        "Reporting manager",
    ),
    str(ProfilePaths.POSITION_JOB_TITLE): ("Jobtitel", "Job title"),
    str(ProfilePaths.POSITION_ROLE_SUMMARY): ("Rollen-Zusammenfassung", "Role summary"),
    str(ProfilePaths.META_TARGET_START_DATE): ("Startdatum", "Start date"),
    "responsibilities.items": ("Kernaufgaben", "Core responsibilities"),
    "requirements.hard_skills_required": ("Muss-Have-Skills", "Must-have skills"),
    "requirements.soft_skills_required": ("Muss-Have-Soft-Skills", "Must-have soft skills"),
}

_MISSING_FIELD_ICON: Final[str] = "⚠️"


def _lookup_field_label(field_path: str, lang: str) -> str:
    """Return a localized label for ``field_path``.

    Falls back to a humanized path when no explicit mapping exists.
    """

    mapped_label = _REQUIRED_FIELD_LABELS.get(field_path)
    if mapped_label:
        return tr(*mapped_label, lang=lang)

    cleaned = field_path.replace("_", " ").replace(".", " ").strip()
    readable = " ".join(part.capitalize() for part in cleaned.split()) or field_path
    return tr(readable, readable, lang=lang)


def _lookup_field_reason(field_path: str, lang: str) -> str:
    """Return a localized rationale for the missing field."""

    prompt_config = CRITICAL_FIELD_PROMPTS.get(field_path)
    if prompt_config:
        description = prompt_config.get("description")
        if isinstance(description, (list, tuple)):
            return tr(*description, lang=lang)
        prompt = prompt_config.get("prompt")
        if isinstance(prompt, (list, tuple)):
            return tr(*prompt, lang=lang)

    return tr(
        "Benötigt für Exporte und Folgeprozesse.",
        "Required for exports and downstream steps.",
        lang=lang,
    )


def build_missing_field_descriptors(
    missing_fields: Collection[str],
) -> list[dict[str, str]]:
    """Return structured descriptors for ``missing_fields`` with labels and reasons."""

    lang = st.session_state.get("lang", "de")
    descriptors: list[dict[str, str]] = []
    seen: set[str] = set()
    for field_path in missing_fields:
        if not field_path or field_path in seen:
            continue
        label = _lookup_field_label(field_path, lang)
        reason = _lookup_field_reason(field_path, lang)
        descriptors.append({"field": field_path, "label": label, "reason": reason})
        seen.add(field_path)
    return descriptors


def format_missing_label(label: str, *, field_path: str, missing_fields: Collection[str]) -> str:
    """Prefix ``label`` with a warning indicator when ``field_path`` is missing."""

    if field_path not in missing_fields:
        return label
    return f"{_MISSING_FIELD_ICON} {label}"


def merge_missing_help(help_text: str | None, *, field_path: str, missing_fields: Collection[str]) -> str | None:
    """Append a localized missing-field hint to ``help_text`` when relevant."""

    if field_path not in missing_fields:
        return help_text

    lang = st.session_state.get("lang", "de")
    reason = _lookup_field_reason(field_path, lang)
    missing_hint = tr(
        "Pflichtfeld: {reason}",
        "Critical field: {reason}",
        lang=lang,
    ).format(reason=reason)

    parts = [text for text in (help_text, missing_hint) if text]
    if not parts:
        return None
    return "\n\n".join(parts)


def render_missing_field_summary(missing_fields: Collection[str], *, scope: Literal["step", "global"] = "step") -> None:
    """Render a highlighted summary for missing critical fields."""

    descriptors = build_missing_field_descriptors(missing_fields)
    if not descriptors:
        return

    lang = st.session_state.get("lang", "de")
    intro = (
        tr(
            "Bitte ergänze diese Angaben in diesem Abschnitt.",
            "Please fill these items in this section.",
            lang=lang,
        )
        if scope == "step"
        else tr(
            "Diese Felder fehlen noch insgesamt, bevor Exporte vollständig sind.",
            "These fields are still missing overall before exports are complete.",
            lang=lang,
        )
    )

    items = "".join(
        (
            "<li>"
            f"<span class='missing-summary__label'>{html.escape(item['label'])}</span>"
            f"<div class='missing-summary__reason'>{html.escape(item['reason'])}</div>"
            "</li>"
        )
        for item in descriptors
    )

    st.markdown(
        """
<div class="missing-summary-panel">
  <div class="missing-summary-panel__title">⚠️ {title}</div>
  <div class="missing-summary-panel__intro">{intro}</div>
  <ul class="missing-summary-panel__list">{items}</ul>
</div>
        """.format(
            title=tr("Fehlende Pflichtfelder", "Missing critical fields", lang=lang),
            intro=html.escape(intro),
            items=items,
        ),
        unsafe_allow_html=True,
    )


def _format_missing_field_list(fields: Iterable[str]) -> str:
    lang = st.session_state.get("lang", "de")
    labels = []
    for field_path in fields:
        label = _REQUIRED_FIELD_LABELS.get(field_path)
        if label:
            labels.append(tr(*label, lang=lang))
        else:
            labels.append(field_path)
    unique_labels = list(dict.fromkeys(labels))
    if not unique_labels:
        return ""
    if len(unique_labels) == 1:
        return unique_labels[0]
    if lang == "de":
        return ", ".join(unique_labels[:-1]) + " und " + unique_labels[-1]
    return ", ".join(unique_labels[:-1]) + " and " + unique_labels[-1]


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
    render_origin_label_html,
    with_ai_badge,
)
from ._widget_state import _ensure_widget_state


_SALARY_SLIDER_STYLE_KEY = "ui.salary.slider_style_injected"


@dataclass(frozen=True)
class OnboardingHeroCopy:
    """Copy bundle for the onboarding hero."""

    eyebrow: str
    title: str
    subtitle: str
    cta_label: str
    timeline: tuple["OnboardingHeroTimelineItem", ...]


@dataclass(frozen=True)
class OnboardingHeroTimelineItem:
    """Content for a single onboarding hero timeline entry."""

    icon: str
    title: str
    description: str


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
    ai_source: str = "wizard_autofill",
    ai_model: str | None = None,
    ai_timestamp: datetime | None = None,
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
            _update_profile(
                field_path,
                cleaned_suggestion,
                mark_ai=True,
                ai_source=ai_source,
                ai_model=ai_model,
                ai_timestamp=ai_timestamp,
            )
            st.toast(success_message, icon=success_icon)
            st.rerun()
        if reject_col.button(
            reject_label,
            key=f"autofill.reject.{field_path}.{suggestion_hash}",
        ):
            _record_autofill_rejection(field_path, cleaned_suggestion)
            st.toast(rejection_message, icon=rejection_icon)
            st.rerun()


def render_navigation_controls(state: NavigationState, *, location: Literal["top", "bottom"] = "bottom") -> None:
    """Render the navigation controls based on ``state``.

    Args:
        state: The navigation state for the current step.
        location: Whether the controls are rendered at the top or bottom of the page.
    """

    marker_class = f"wizard-nav-marker wizard-nav-marker--{location}"
    st.markdown(f"<div class='{marker_class}'></div>", unsafe_allow_html=True)
    cols = st.columns((1, 1), gap="small")
    _render_navigation_button(cols[0], state.previous, state, location=location)
    _render_navigation_button(cols[1], state.next, state, location=location)


def _render_navigation_button(
    column: DeltaGenerator,
    button: NavigationButtonState | None,
    state: NavigationState,
    *,
    location: Literal["top", "bottom"],
) -> None:
    """Render a single navigation button if configured."""

    if button is None:
        column.write("")
        return

    label = tr(*button.label)
    key = f"wizard_{button.direction.value}_{state.current_key}_{location}"
    button_type: Literal["primary", "secondary"] = "primary" if button.primary else "secondary"
    wrapper_open = False
    if button.direction is NavigationDirection.NEXT:
        modifier = "enabled" if button.enabled else "disabled"
        column.markdown(
            f"<div class='wizard-nav-next wizard-nav-next--{modifier}'>",
            unsafe_allow_html=True,
        )
        wrapper_open = True

    use_form_submit = bool(st.session_state.get(StateKeys.WIZARD_STEP_FORM_MODE))
    if use_form_submit:
        triggered = column.form_submit_button(
            label,
            key=key,
            type=button_type,
            disabled=not button.enabled,
            use_container_width=True,
        )
    else:
        triggered = column.button(
            label,
            key=key,
            type=button_type,
            disabled=not button.enabled,
            use_container_width=True,
        )

    if wrapper_open:
        column.markdown("</div>", unsafe_allow_html=True)

    if triggered and button.direction is NavigationDirection.NEXT and state.missing_fields:
        missing_fields = _format_missing_field_list(state.missing_fields)
        warning_message = tr(
            "Bitte fülle die erforderlichen Felder aus: {fields}.",
            "Please complete the required fields: {fields}.",
        ).format(fields=missing_fields)
        st.warning(warning_message)
        return

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


def build_onboarding_hero_copy(
    *,
    format_message: Callable[..., str],
    profile_context: Mapping[str, str],
) -> OnboardingHeroCopy:
    """Build the localized onboarding hero copy from the shared templates."""

    eyebrow = tr(
        "Cognitive Staffing · Recruiting-Bedarfsanalyse",
        "Cognitive Staffing · Recruitment Need Analysis",
    )
    title = format_message(
        default=(
            "Vom Bedarf zur klaren Rollenbeschreibung.",
            "From hiring need to a clear role brief.",
        ),
        context=profile_context,
        variants=[],
    )
    subtitle = format_message(
        default=(
            "Wizard-Flow, Markt- & Gehaltsdaten und ESCO-Mapping bündeln Evidenz für sichere Entscheidungen.",
            "Wizard flow, market & salary data, plus ESCO mapping combine evidence for confident decisions.",
        ),
        context=profile_context,
        variants=[],
    )
    cta_label = tr("Jetzt analysieren", "Start analysis")
    timeline = (
        OnboardingHeroTimelineItem(
            icon="🧭",
            title=tr("Wizard-Flow", "Wizard flow"),
            description=tr(
                "Anforderungen Schritt für Schritt definieren.",
                "Define requirements step by step.",
            ),
        ),
        OnboardingHeroTimelineItem(
            icon="📊",
            title=tr("Markt & Gehalt", "Market & salary"),
            description=tr(
                "Seniorität und Spannen aus Benchmarks ableiten.",
                "Benchmark seniority and compensation ranges.",
            ),
        ),
        OnboardingHeroTimelineItem(
            icon="🧩",
            title=tr("ESCO-Mapping", "ESCO mapping"),
            description=tr(
                "Skills sauber zu ESCO-Standards zuordnen.",
                "Align skills with ESCO standards.",
            ),
        ),
    )
    return OnboardingHeroCopy(
        eyebrow=eyebrow,
        title=title,
        subtitle=subtitle,
        cta_label=cta_label,
        timeline=timeline,
    )


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


def render_onboarding_hero(
    animation_bytes: bytes | None,
    *,
    hero_copy: OnboardingHeroCopy,
    mime_type: str = "image/gif",
) -> None:
    """Render the onboarding hero with logo and positioning copy."""

    if not animation_bytes:
        return

    animation_base64 = b64encode(animation_bytes).decode("ascii")

    hero_eyebrow = html.escape(hero_copy.eyebrow)
    hero_title = html.escape(hero_copy.title)
    hero_subtitle = html.escape(hero_copy.subtitle)
    hero_cta_label = html.escape(hero_copy.cta_label)
    hero_mime_type = html.escape(mime_type)
    hero_animation_base64 = html.escape(animation_base64)
    timeline_items = "".join(
        (
            "<li class='onboarding-hero__timeline-item'>"
            f"<span class='onboarding-hero__timeline-icon'>{html.escape(item.icon)}</span>"
            f"<div class='onboarding-hero__timeline-title'>{html.escape(item.title)}</div>"
            f"<div class='onboarding-hero__timeline-description'>{html.escape(item.description)}</div>"
            "</li>"
        )
        for item in hero_copy.timeline
    )

    hero_html = f"""
    <div class="onboarding-hero">
        <div class="onboarding-hero__logo">
            <img src="data:{hero_mime_type};base64,{hero_animation_base64}" alt="Cognitive Staffing — Recruitment Need Analysis" />
        </div>
        <div class="onboarding-hero__copy">
            <div class="onboarding-hero__eyebrow">{hero_eyebrow}</div>
            <h1 class="onboarding-hero__headline">{hero_title}</h1>
            <p class="onboarding-hero__subheadline">{hero_subtitle}</p>
            <div class="onboarding-hero__actions">
                <a class="onboarding-hero__cta" href="#onboarding-source">{hero_cta_label}</a>
            </div>
            <ul class="onboarding-hero__timeline">{timeline_items}</ul>
        </div>
    </div>
    """

    st.markdown(hero_html, unsafe_allow_html=True)


def render_step_heading(
    title: str,
    subtitle: Optional[str] = None,
    *,
    missing_fields: Collection[str] | None = None,
) -> None:
    """Render a consistent heading block for wizard steps."""

    lang = st.session_state.get("lang", "de")
    missing = tuple(missing_fields or ())

    if missing:
        title_col, badge_col = st.columns((0.85, 0.15))
        with title_col:
            st.header(title)
        badge_label = tr(
            "Pflichtfelder fehlen",
            "Critical fields missing",
            lang=lang,
        )
        badge_col.markdown(
            f"""
            <div style="display: flex; justify-content: flex-end;">
                <div class='missing-badge'>
                    {_MISSING_FIELD_ICON} {badge_label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
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


def _coerce_path_list(candidate: Any) -> list[str]:
    """Return a list of strings from ``candidate`` when feasible."""

    if isinstance(candidate, str):
        return [candidate]
    if isinstance(candidate, (list, tuple, set, frozenset)):
        return [str(item) for item in candidate if isinstance(item, str) and item]
    return []


def _humanize_schema_path(path: str, lang: str | None) -> str:
    """Return a localized, human-readable version of ``path``."""

    cleaned = path.replace(".", " ").replace("_", " ").strip()
    label = " ".join(part.capitalize() for part in cleaned.split()) or path
    return tr(label, label, lang=lang)


def _format_profile_repair_warning(summary: Any, lang: str | None) -> str | None:
    """Build a bilingual warning message for auto-populated/removed fields."""

    if not isinstance(summary, Mapping):
        return None
    auto_fields = _coerce_path_list(summary.get("auto_populated"))
    removed_fields = _coerce_path_list(summary.get("removed"))
    if not auto_fields and not removed_fields:
        return None

    base = tr(
        "Einige Felder wurden aufgrund von Validierungsfehlern automatisch befüllt oder zurückgesetzt.",
        "Some fields were automatically populated or reset due to validation errors.",
        lang=lang,
    )
    field_segments: list[str] = []
    if auto_fields:
        auto_label = tr("Automatisch befüllt", "Auto-filled", lang=lang)
        readable = ", ".join(_humanize_schema_path(path, lang) for path in auto_fields)
        field_segments.append(f"{auto_label}: {readable}")
    if removed_fields:
        removed_label = tr("Entfernt", "Removed", lang=lang)
        readable = ", ".join(_humanize_schema_path(path, lang) for path in removed_fields)
        field_segments.append(f"{removed_label}: {readable}")
    detail_text = " – ".join(field_segments)
    review_prompt = tr(
        "Bitte überprüfen Sie diese Felder.",
        "Please double-check these fields.",
        lang=lang,
    )
    return " ".join(part for part in (base, detail_text, review_prompt) if part)


_WARNING_STYLES: Final[str] = """
<style>
.wizard-warning-drawer {
  position: fixed;
  bottom: 1rem;
  left: 0;
  right: 0;
  margin: 0 auto;
  width: min(var(--container-max-width, 1100px), 96vw);
  z-index: 20;
  background: var(--surface-1, #0a1730);
  border: 1px solid var(--border-subtle, rgba(95, 210, 255, 0.24));
  border-radius: var(--radius-md, 18px);
  box-shadow: var(--shadow-medium, 0 28px 58px rgba(2, 6, 18, 0.56));
  overflow: hidden;
  color: var(--color-text-strong, #f4f9ff);
}

.wizard-warning-drawer summary {
  cursor: pointer;
  list-style: none;
  padding: 0.85rem 1.1rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.wizard-warning-drawer summary::-webkit-details-marker {
  display: none;
}

.wizard-warning-body {
  padding: 0.25rem 1.1rem 1rem;
  background: var(--surface-2, rgba(15, 35, 68, 0.92));
  border-top: 1px solid var(--border-subtle, rgba(95, 210, 255, 0.18));
}

.wizard-warning-body ul {
  padding-left: 1.2rem;
  margin: 0.35rem 0 0;
}

.wizard-warning-body li {
  margin-bottom: 0.35rem;
  line-height: 1.5;
}

.wizard-warning-hint {
  margin: 0;
  color: var(--text-muted, rgba(233, 242, 255, 0.82));
  font-size: 0.95rem;
}
</style>
"""


def _render_collapsed_warning(messages: list[str], lang: str | None) -> None:
    """Render auto-repair warnings collapsed at the bottom of the viewport."""

    if not messages:
        return

    if not st.session_state.get("_wizard_warning_css_injected"):
        st.session_state["_wizard_warning_css_injected"] = True
        st.markdown(_WARNING_STYLES, unsafe_allow_html=True)

    summary_label = tr("Validierungshinweise", "Validation notices", lang=lang)
    detail_hint = tr(
        "Automatisch angepasste Felder – zum Prüfen ausklappen.",
        "Auto-adjusted fields – expand to review.",
        lang=lang,
    )

    def _normalize(message: str) -> str:
        sanitized = html.escape(message)
        return sanitized.replace("\n", "<br/>")

    list_items = "".join(f"<li>{_normalize(message)}</li>" for message in messages)
    warning_html = f"""
<details class="wizard-warning-drawer">
  <summary>⚠️ {summary_label}</summary>
  <div class="wizard-warning-body">
    <p class="wizard-warning-hint">{detail_hint}</p>
    <ul>{list_items}</ul>
  </div>
</details>
"""

    st.markdown(warning_html, unsafe_allow_html=True)


def render_step_warning_banner() -> None:
    """Display a bilingual warning banner when extraction repairs are active."""

    lang = st.session_state.get("lang")
    warning_text = st.session_state.get(StateKeys.STEPPER_WARNING)
    extraction_summary = st.session_state.get(StateKeys.EXTRACTION_SUMMARY)
    detail_text = _extract_warning_details(extraction_summary, warning_text or "", lang)
    repair_summary = st.session_state.get(StateKeys.PROFILE_REPAIR_FIELDS)
    repair_message = _format_profile_repair_warning(repair_summary, lang)

    messages: list[str] = []
    if isinstance(warning_text, str) and warning_text.strip():
        if detail_text:
            detail_label = tr("Details", "Details", lang=lang)
            messages.append(f"{warning_text}\n\n{detail_label}:\n{detail_text}")
        else:
            messages.append(warning_text)
    if repair_message:
        messages.append(repair_message)
    if not messages:
        return

    _render_collapsed_warning(messages, lang)


def _default_list_text_area_height(items: Sequence[str] | None) -> int:
    """Return a height that grows with the existing list size."""

    item_count = len([item for item in (items or []) if isinstance(item, str) and item.strip()])
    if item_count <= 2:
        return 220
    return min(720, 28 * (item_count + 1))


def render_list_text_area(
    *,
    label: str,
    field_path: str | None = None,
    session_key: str,
    items: Sequence[str] | None = None,
    placeholder: str | None = None,
    height: int | None = None,
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
        "height": height if height is not None else _default_list_text_area_height(items),
    }
    if placeholder:
        widget_args["placeholder"] = placeholder

    if field_path:
        decorated_label, updated_help = with_ai_badge(label, field_path, help_text=widget_args.get("help"))
        widget_args["label"] = decorated_label
        if updated_help is not None:
            widget_args["help"] = updated_help
        origin_label = render_origin_label_html(decorated_label, field_path)
        if origin_label:
            st.markdown(origin_label, unsafe_allow_html=True)
            widget_args.setdefault("label_visibility", "collapsed")

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
    "OnboardingHeroCopy",
    "OnboardingHeroTimelineItem",
    "NavigationButtonState",
    "NavigationDirection",
    "NavigationState",
    "build_onboarding_hero_copy",
    "render_list_text_area",
    "render_navigation_controls",
    "inject_salary_slider_styles",
    "build_missing_field_descriptors",
    "format_missing_label",
    "merge_missing_help",
    "render_missing_field_summary",
    "render_onboarding_hero",
    "render_section_heading",
    "render_step_heading",
    "render_step_warning_banner",
]
