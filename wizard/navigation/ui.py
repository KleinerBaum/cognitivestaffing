from __future__ import annotations

import html
from typing import Callable, Literal, Sequence

import streamlit as st

from components.stepper import render_stepper
from utils.i18n import tr
from wizard.layout import (
    NavigationButtonState,
    NavigationDirection,
    NavigationState,
    render_navigation_controls,
)
from wizard.types import LocalizedText
from wizard_pages.base import WizardPage


_NAVIGATION_STYLE = """
<style>
.wizard-nav-marker + div[data-testid="stHorizontalBlock"] {
    display: flex;
    justify-content: center;
    gap: var(--space-sm, 0.6rem);
    align-items: stretch;
    margin: 1.2rem auto 0.65rem;
    max-width: 520px;
}

.wizard-nav-marker--top + div[data-testid="stHorizontalBlock"] {
    margin: 0 auto 0.9rem;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex: 1 1 0;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next button {
    min-height: 3rem;
    font-size: 1.02rem;
    font-weight: 650;
    transition:
        box-shadow var(--transition-base, 0.18s ease-out),
        transform var(--transition-base, 0.18s ease-out),
        background-color var(--transition-base, 0.18s ease-out);
    will-change: transform, box-shadow;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] button {
    width: 100%;
    border-radius: 14px;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next button[kind="primary"] {
    box-shadow: 0 16px 32px rgba(37, 58, 95, 0.2);
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next--enabled button[kind="primary"] {
    animation: wizardNavPulse 1.2s ease-out 1;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next button[kind="primary"]:hover:not(:disabled) {
    box-shadow: 0 20px 40px rgba(37, 58, 95, 0.26);
    transform: translateY(-1px);
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next button:disabled {
    box-shadow: none;
    opacity: 0.55;
}

.wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next--disabled button {
    transform: none;
}

.wizard-nav-hint {
    margin-top: 0.35rem;
    color: var(--text-soft, rgba(15, 23, 42, 0.7));
    font-size: 0.9rem;
}

.wizard-nav-warning-area {
    margin: 0.45rem auto 0;
    max-width: 520px;
}

.wizard-nav-warning {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    min-height: 3rem;
    padding: 0.6rem 0.85rem;
    border-radius: 12px;
    border: 1px solid rgba(245, 158, 11, 0.35);
    background: rgba(251, 191, 36, 0.18);
    color: var(--text-primary, rgba(15, 23, 42, 0.92));
    font-size: 0.92rem;
    line-height: 1.35;
    box-sizing: border-box;
    max-height: 6rem;
    overflow-y: auto;
}

.wizard-nav-warning--empty {
    border-color: transparent;
    background: transparent;
    padding: 0;
}

@media (max-width: 768px) {
    .wizard-nav-marker + div[data-testid="stHorizontalBlock"] {
        flex-direction: column;
    }

    .wizard-nav-marker + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: 100%;
    }

    .wizard-nav-marker + div[data-testid="stHorizontalBlock"] .wizard-nav-next button {
        position: sticky;
        bottom: 1rem;
        z-index: 10;
        box-shadow: 0 16px 32px rgba(15, 23, 42, 0.22);
    }

    .wizard-nav-marker--top + div[data-testid="stHorizontalBlock"] .wizard-nav-next button {
        position: static;
        box-shadow: 0 16px 32px rgba(37, 58, 95, 0.2);
    }

    .wizard-nav-marker + div[data-testid="stHorizontalBlock"] button {
        min-height: 3rem;
    }
}

@keyframes wizardNavPulse {
    0% {
        box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.0);
        transform: scale(0.995);
    }
    40% {
        box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.15);
        transform: scale(1.01);
    }
    100% {
        box-shadow: 0 16px 32px rgba(37, 58, 95, 0.2);
        transform: scale(1);
    }
}
</style>
"""


def inject_navigation_style() -> None:
    st.markdown(_NAVIGATION_STYLE, unsafe_allow_html=True)


def build_navigation_state(
    *,
    page: WizardPage,
    missing: Sequence[str],
    previous_key: str | None,
    next_key: str | None,
    allow_skip: bool,
    navigate_factory: Callable[[str, bool, bool], Callable[[], None]],
) -> NavigationState:
    missing_tuple = tuple(missing)

    def _nav_callback(
        target: str,
        *,
        mark_complete: bool = False,
        skipped: bool = False,
    ) -> Callable[[], None]:
        def _run() -> None:
            navigate_factory(target, mark_complete, skipped)()

        return _run

    previous_button = (
        NavigationButtonState(
            direction=NavigationDirection.PREVIOUS,
            label=("◀ Zurück", "◀ Back"),
            target_key=previous_key,
            on_click=_nav_callback(previous_key),
        )
        if previous_key
        else None
    )

    if next_key:
        next_hint: LocalizedText | None = None
        next_enabled = True
        if missing_tuple:
            next_hint = (
                "Bitte fülle die markierten Pflichtfelder aus, bevor du fortfährst.",
                "Please complete the marked required fields before continuing.",
            )
            next_enabled = allow_skip
        next_button = NavigationButtonState(
            direction=NavigationDirection.NEXT,
            label=("Weiter ▶", "Next ▶"),
            target_key=next_key,
            enabled=next_enabled,
            primary=True,
            hint=next_hint,
            on_click=_nav_callback(next_key, mark_complete=True),
        )
    else:
        next_button = None

    skip_button = None
    if allow_skip and next_key:
        skip_button = NavigationButtonState(
            direction=NavigationDirection.SKIP,
            label=("Überspringen", "Skip"),
            target_key=next_key,
            on_click=_nav_callback(next_key, mark_complete=True, skipped=True),
        )

    return NavigationState(
        current_key=page.key,
        missing_fields=missing_tuple,
        previous=previous_button,
        next=next_button,
        skip=skip_button,
    )


def render_navigation(state: NavigationState, *, location: Literal["top", "bottom"] = "bottom") -> None:
    """Render wizard navigation controls.

    Args:
        state: The current navigation state.
        location: Whether to place the controls at the top or bottom of the step.
    """

    if location == "bottom":
        summary = st.session_state.get("_wizard_step_summary")
        if summary:
            try:
                current, labels = summary
            except (TypeError, ValueError):
                current, labels = None, None
            if (
                isinstance(current, int | str)
                and isinstance(labels, Sequence)
                and not isinstance(labels, str)
                and labels
            ):
                try:
                    current_index = int(current)
                except (TypeError, ValueError):
                    current_index = 0
                render_stepper(current_index, [str(label) for label in labels])

    render_navigation_controls(state, location=location)


def render_validation_warnings(pending_validation_errors: dict[str, LocalizedText]) -> None:
    messages = list(dict.fromkeys(pending_validation_errors.values())) if pending_validation_errors else []
    lang = st.session_state.get("lang", "de")
    combined = "\n\n".join(tr(de, en, lang=lang) for de, en in messages)
    sanitized = html.escape(combined).replace("\n", "<br />")
    warning_class = "wizard-nav-warning--active" if combined.strip() else "wizard-nav-warning--empty"
    st.markdown(
        f"""
        <div class="wizard-nav-warning-area">
            <div class="wizard-nav-warning {warning_class}">
                {sanitized}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def maybe_scroll_to_top() -> None:
    if not st.session_state.pop("_wizard_scroll_to_top", False):
        return
    st.markdown(
        """
        <script>
        (function() {
            const root = window;
            const target = root.document.querySelector('section.main');
            const scrollToTop = () => {
                if (!target) {
                    root.scrollTo({ top: 0, behavior: 'smooth' });
                    return;
                }
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                setTimeout(() => {
                    target.setAttribute('tabindex', '-1');
                    target.focus({ preventScroll: true });
                }, 180);
            };
            if ('requestAnimationFrame' in root) {
                root.requestAnimationFrame(scrollToTop);
            } else {
                scrollToTop();
            }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


__all__ = [
    "build_navigation_state",
    "inject_navigation_style",
    "maybe_scroll_to_top",
    "render_navigation",
    "render_validation_warnings",
]
