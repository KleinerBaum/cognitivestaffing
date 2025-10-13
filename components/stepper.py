"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st


_STYLE_STATE_KEY = "_workflow_stepper_styles_v1"


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
            margin-bottom: 0.5rem;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"] {
            flex: 1;
            position: relative;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"]::after {
            content: "";
            position: absolute;
            top: 50%;
            right: -0.375rem;
            width: 0.75rem;
            height: 1px;
            background: linear-gradient(
                90deg,
                rgba(148, 163, 184, 0.35),
                rgba(148, 163, 184, 0)
            );
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            > div[data-testid="column"]:last-child::after {
            display: none;
        }

        .workflow-stepper__step {
            height: 100%;
        }

        .workflow-stepper__step button[kind="secondary"] {
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.25);
            background: rgba(15, 23, 42, 0.1);
            color: var(--workflow-step-text, #e2e8f0);
            font-weight: 600;
            justify-content: flex-start;
            gap: 0.5rem;
            padding: 0.65rem 0.9rem;
        }

        .workflow-stepper__step button[kind="secondary"]:hover:not(:disabled) {
            border-color: rgba(148, 163, 184, 0.45);
            background: rgba(30, 41, 59, 0.2);
        }

        .workflow-stepper__step--done button[kind="secondary"] {
            border-color: rgba(45, 212, 191, 0.35);
            background: rgba(45, 212, 191, 0.12);
            color: #c4f5ed;
        }

        .workflow-stepper__step--current button[kind="secondary"] {
            border-color: rgba(129, 140, 248, 0.45);
            background: rgba(129, 140, 248, 0.18);
            color: #dbeafe;
        }

        .workflow-stepper__step--upcoming button[kind="secondary"] {
            border-color: rgba(148, 163, 184, 0.18);
            background: rgba(15, 23, 42, 0.05);
            color: rgba(226, 232, 240, 0.72);
        }

        .workflow-stepper__step--upcoming
            button[kind="secondary"]:hover:not(:disabled) {
            border-color: rgba(148, 163, 184, 0.35);
            background: rgba(30, 41, 59, 0.15);
        }

        .workflow-stepper__step button[kind="secondary"][disabled] {
            opacity: 0.95;
        }

        .workflow-stepper-marker
            + div[data-testid="stHorizontalBlock"]
            button span {
            white-space: normal;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(
    current: int,
    labels: Sequence[str],
    *,
    on_select: Callable[[int], None] | None = None,
) -> None:
    """Render a progress indicator with contextual labels.

    Args:
        current: Current step index (0-based).
        labels: Ordered list of step labels.
        on_select: Optional callback invoked when the user requests a step
            change. Receives the selected index.
    """

    total = len(labels)
    if total == 0:
        return

    _inject_workflow_styles()

    status_icons = {
        "done": "✔︎",
        "current": "➤",
        "upcoming": "•",
    }

    with st.container():
        st.markdown(
            "<div class='workflow-stepper-marker'></div>",
            unsafe_allow_html=True,
        )
        annotated_steps: list[str] = []
        for start in range(0, total, 3):
            chunk = labels[start : start + 3]
            columns = st.columns([1] * len(chunk), gap="small")

            for offset, (column, label) in enumerate(zip(columns, chunk)):
                idx = start + offset
                button_label = f"{idx + 1}. {label}"
                if idx < current:
                    status = "done"
                elif idx == current:
                    status = "current"
                else:
                    status = "upcoming"

                icon = status_icons[status]
                annotated_label = f"{icon} {button_label}"
                annotated_steps.append(
                    f"**{annotated_label}**" if status == "current" else annotated_label
                )

                disabled = status == "current" or on_select is None
                with column:
                    st.markdown(
                        f"<div class='workflow-stepper__step workflow-stepper__step--{status}'>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        annotated_label,
                        key=f"wizard_stepper_{idx}",
                        use_container_width=True,
                        type="secondary",
                        disabled=disabled,
                    ):
                        if on_select is not None and not disabled:
                            on_select(idx)
                    st.markdown("</div>", unsafe_allow_html=True)

    st.caption(" → ".join(annotated_steps))
