"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

import html
from typing import Callable, Sequence

import streamlit as st


_STYLE_STATE_KEY = "_workflow_stepper_styles_v2"

_STEP_KEYCAPS = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}


STEP_NAVIGATION_ENABLED = True


def _inject_workflow_styles() -> None:
    """Inject subtle workflow styling for the wizard stepper once per session."""

    if st.session_state.get(_STYLE_STATE_KEY):
        return

    st.session_state[_STYLE_STATE_KEY] = True
    st.markdown(
        """
        <style>
        .wizard-stepper-shell {
            margin: 0.35rem 0 0.9rem;
        }

        .wizard-emoji-stepper {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
            min-height: 2.5rem;
        }

        .wizard-emoji-stepper__step {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
            border: 1px solid var(--border-subtle);
            background: var(--interactive-surface);
            color: var(--text-soft);
            font-weight: 600;
            font-size: 0.9rem;
            line-height: 1.2;
            opacity: 0.62;
            transition:
                opacity var(--transition-base, 0.2s ease),
                transform var(--transition-base, 0.2s ease),
                box-shadow var(--transition-base, 0.2s ease),
                background-color var(--transition-base, 0.2s ease),
                border-color var(--transition-base, 0.2s ease);
            user-select: none;
            white-space: nowrap;
        }

        .wizard-emoji-stepper__step--done {
            opacity: 0.88;
            color: var(--text-strong);
            border-color: var(--interactive-border-strong);
            background: var(--interactive-done);
        }

        .wizard-emoji-stepper__step--active {
            opacity: 1;
            transform: translateY(-1px);
            border-color: var(--interactive-border-strong);
            background: var(--interactive-current);
            color: var(--text-strong);
            box-shadow: 0 6px 14px rgba(3, 8, 20, 0.35);
        }

        .wizard-emoji-stepper__step--upcoming {
            opacity: 0.52;
        }

        .wizard-emoji-stepper__icon {
            font-size: 1.05rem;
        }

        @media (max-width: 900px) {
            .wizard-emoji-stepper {
                gap: 0.45rem;
            }

            .wizard-emoji-stepper__step {
                width: 100%;
                justify-content: flex-start;
                white-space: normal;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .wizard-emoji-stepper__step {
                transition: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _step_keycap(index: int) -> str:
    return _STEP_KEYCAPS.get(index, f"{index}.")


def _build_stepper_segments(current: int, labels: Sequence[str]) -> list[str]:
    """Return HTML segments representing the emoji stepper."""

    segments: list[str] = []
    for idx, label in enumerate(labels):
        if idx < current:
            state = "done"
        elif idx == current:
            state = "active"
        else:
            state = "upcoming"
        keycap = _step_keycap(idx + 1)
        safe_label = html.escape(label)
        aria_current = " aria-current='step'" if state == "active" else ""
        segments.append(
            (
                "<span class='wizard-emoji-stepper__step wizard-emoji-stepper__step--"
                f"{state}' role='listitem'{aria_current}>"
                f"<span class='wizard-emoji-stepper__icon' aria-hidden='true'>{keycap}</span>"
                f"<span class='wizard-emoji-stepper__label'>{safe_label}</span>"
                "</span>"
            )
        )
    return segments


def render_step_summary(current: int, labels: Sequence[str]) -> None:
    """Render the emoji stepper summary."""

    render_stepper(current, labels)


def render_stepper(
    current: int,
    labels: Sequence[str],
    *,
    on_select: Callable[[int], None] | None = None,
) -> None:
    """Render the emoji stepper for wizard navigation."""

    if not STEP_NAVIGATION_ENABLED or not labels:
        return

    _inject_workflow_styles()
    segments = _build_stepper_segments(current, labels)
    if not segments:
        return

    st.markdown(
        "<div class='wizard-stepper-shell'>"
        "<div class='wizard-emoji-stepper' role='list'>" + "".join(segments) + "</div></div>",
        unsafe_allow_html=True,
    )
