"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

import streamlit as st


def render_stepper(current: int, labels: list[str]) -> None:
    """Render a progress indicator with contextual labels.

    Args:
        current: Current step index (0-based).
        labels: Ordered list of step labels.
    """

    total = len(labels)
    if total == 0:
        return

    progress = (current + 1) / total
    st.progress(progress)

    annotated_steps: list[str] = []
    for idx, label in enumerate(labels):
        prefix = f"{idx + 1}."
        if idx == current:
            annotated_steps.append(f"**{prefix} {label}**")
        else:
            annotated_steps.append(f"{prefix} {label}")

    st.caption(" → ".join(annotated_steps))
