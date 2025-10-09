"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st


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

    progress = (current + 1) / total
    st.progress(progress)

    columns = st.columns(total)
    annotated_steps: list[str] = []
    for idx, (column, label) in enumerate(zip(columns, labels)):
        button_label = f"{idx + 1}. {label}"
        is_current = idx == current
        annotated_steps.append(f"**{button_label}**" if is_current else button_label)

        disabled = is_current or on_select is None
        button_type = "primary" if is_current else "secondary"
        with column:
            if st.button(
                button_label,
                key=f"wizard_stepper_{idx}",
                use_container_width=True,
                type=button_type,
                disabled=disabled,
            ):
                if on_select is not None and not disabled:
                    on_select(idx)

    st.caption(" → ".join(annotated_steps))
