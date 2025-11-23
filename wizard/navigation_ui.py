from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

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
    gap: var(--space-sm, 0.6rem);
    align-items: stretch;
    margin: 1.2rem 0 0.65rem;
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
        if missing_tuple:
            next_hint = (
                "Pflichtfelder fehlen – du kannst trotzdem weitergehen und später ergänzen.",
                "Required fields are missing — you can continue and fill them later.",
            )
        enabled = not missing_tuple
        next_button = NavigationButtonState(
            direction=NavigationDirection.NEXT,
            label=("Weiter ▶", "Next ▶"),
            target_key=next_key,
            enabled=enabled,
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


def render_navigation(state: NavigationState) -> None:
    render_navigation_controls(state)


def render_validation_warnings(pending_validation_errors: dict[str, LocalizedText]) -> None:
    if not pending_validation_errors:
        return
    messages = list(dict.fromkeys(pending_validation_errors.values()))
    if not messages:
        return
    lang = st.session_state.get("lang", "de")
    combined = "\n\n".join(tr(de, en, lang=lang) for de, en in messages)
    if combined.strip():
        st.warning(combined)


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
