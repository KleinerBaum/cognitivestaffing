"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

import html
from typing import Callable, Sequence

import streamlit as st


_STYLE_STATE_KEY = "_workflow_stepper_styles_v1"


# The wizard stepper is intentionally disabled to keep the wizard canvas clean.
# Keeping the rendering function as a no-op maintains backward compatibility for
# callers that still import it (e.g., tests that monkeypatch the helper).
STEP_NAVIGATION_ENABLED = False


def _inject_workflow_styles() -> None:
    """Inject subtle workflow styling for the wizard stepper once per session."""

    if st.session_state.get(_STYLE_STATE_KEY):
        return

    st.session_state[_STYLE_STATE_KEY] = True
    st.markdown(
        """
        <style>
        .workflow-stepper-marker + div[data-testid="stHorizontalBlock"] {
            display: flex;
            gap: 0.75rem;
            align-items: stretch;
            margin-bottom: 0.75rem;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"] {
            flex: 1 1 0;
            position: relative;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"]::after {
            content: "";
            position: absolute;
            top: calc(50% - 1px);
            right: -0.375rem;
            width: 0.75rem;
            height: 2px;
            background: linear-gradient(
                90deg,
                var(--border-subtle),
                rgba(0, 0, 0, 0)
            );
            border-radius: 999px;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"]:last-child::after {
            display: none;
        }

        .workflow-stepper__step {
            height: 100%;
            border-radius: 1rem;
            overflow: hidden;
        }

        .workflow-stepper__step button[kind="secondary"] {
            border-radius: 999px;
            border: 1px solid var(--border-subtle);
            background: var(--interactive-surface);
            color: var(--text-strong);
            font-weight: 600;
            justify-content: flex-start;
            gap: 0.5rem;
            padding: 0.65rem 0.9rem;
            transition: all 0.2s ease;
        }

        .workflow-stepper__step button[kind="secondary"]:hover:not(:disabled) {
            border-color: var(--interactive-border-strong);
            background: var(--interactive-hover);
        }

        .workflow-stepper__step--done button[kind="secondary"] {
            border-color: var(--interactive-border-strong);
            background: var(--interactive-done);
            color: var(--text-strong);
            box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.2);
        }

        .workflow-stepper__step--current button[kind="secondary"] {
            border-color: var(--interactive-border-strong);
            background: var(--interactive-current);
            color: var(--text-strong);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35);
        }

        .workflow-stepper__step--upcoming button[kind="secondary"] {
            border-color: var(--border-subtle);
            background: var(--interactive-surface);
            color: var(--text-soft);
        }

        .workflow-stepper__step--upcoming
            button[kind="secondary"]:hover:not(:disabled) {
            border-color: var(--interactive-border-strong);
            background: var(--interactive-hover);
        }

        .workflow-stepper__step button[kind="secondary"][disabled] {
            opacity: 0.95;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            button span {
            white-space: normal;
        }

        .workflow-stepper__summary {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin: 0.25rem 0 0.75rem;
        }

        .workflow-stepper__summary span[data-state="current"] {
            color: var(--text-strong);
            font-weight: 600;
        }

        .workflow-stepper__summary span[data-state="done"] {
            color: var(--text-strong);
        }

        .workflow-stepper__summary span[aria-hidden="true"] {
            color: var(--border-strong);
        }

        @media (max-width: 900px) {
            .workflow-stepper-marker + div[data-testid="stHorizontalBlock"] {
                flex-direction: column;
                gap: 0.65rem;
            }

            .workflow-stepper-marker
                + div[data-testid="stHorizontalBlock"]
                > div[data-testid="column"]::after {
                display: none;
            }

            .workflow-stepper__step button[kind="secondary"] {
                width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_summary_segments(current: int, labels: Sequence[str]) -> list[str]:
    """Return HTML segments representing the wizard step summary."""

    status_icons = {
        "done": "✔︎",
        "current": "➤",
        "upcoming": "•",
    }
    segments: list[str] = []
    for idx, label in enumerate(labels):
        button_label = f"{idx + 1}. {label}"
        if idx < current:
            status = "done"
        elif idx == current:
            status = "current"
        else:
            status = "upcoming"
        icon = status_icons[status]
        annotated_label = f"{icon} {button_label}"
        segments.append(f"<span data-state='{status}'>{html.escape(annotated_label)}</span>")
    return segments


def render_step_summary(current: int, labels: Sequence[str]) -> None:
    """Render the condensed wizard step summary above the step heading."""

    if not STEP_NAVIGATION_ENABLED or not labels:
        return

    _inject_workflow_styles()
    summary_segments = _build_summary_segments(current, labels)
    if not summary_segments:
        return

    arrow = "<span aria-hidden='true'>→</span>"
    st.markdown(
        "<div class='workflow-stepper__summary'>" + arrow.join(summary_segments) + "</div>",
        unsafe_allow_html=True,
    )


def render_stepper(
    current: int,
    labels: Sequence[str],
    *,
    on_select: Callable[[int], None] | None = None,
) -> None:
    """Deprecated wrapper retained for compatibility; renders the summary only."""

    if not STEP_NAVIGATION_ENABLED:
        return

    render_step_summary(current, labels)
