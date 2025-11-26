"""UI helpers for AI skip flow after repeated failures."""

from __future__ import annotations

import streamlit as st

from state.ai_failures import (
    mark_step_ai_skipped,
    should_offer_skip,
)
from utils.i18n import tr


def render_skip_cta(
    step_key: str,
    *,
    lang: str,
    warning_text: tuple[str, str],
    button_key: str,
) -> None:
    """Render a skip warning and button when failures exceed the threshold."""

    if not should_offer_skip(step_key):
        return

    st.warning(tr(*warning_text, lang=lang))
    if st.button(
        tr("KI für diesen Schritt überspringen", "Skip AI for this step", lang=lang),
        key=button_key,
        type="secondary",
    ):
        mark_step_ai_skipped(step_key)
        st.toast(
            tr("AI für diesen Schritt wird übersprungen.", "AI will be skipped for this step.", lang=lang),
            icon="⚠️",
        )
        st.rerun()


def render_skipped_banner(_step_key: str, *, lang: str, message: tuple[str, str]) -> None:
    """Show a notice when AI suggestions were explicitly skipped."""

    st.info(tr(*message, lang=lang), icon="⚠️")
