"""Helpers for standard step layouts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import streamlit as st

from utils.i18n import tr
from wizard.layout import render_missing_field_summary


LocalizedText = str | tuple[str, str]


def _resolve_text(text: LocalizedText, *, lang: str) -> str:
    if isinstance(text, str):
        return text
    return tr(*text, lang=lang)


def render_step_layout(
    title: LocalizedText,
    intro: LocalizedText | None,
    *,
    known_cb: Callable[[], None],
    missing_cb: Callable[[], None] | None = None,
    missing_paths: Sequence[str] | None = None,
    tools_cb: Callable[[], None] | None = None,
) -> None:
    """Render a standard step layout with Known/Missing/Validate sections."""

    # GREP:STEP_LAYOUT_V2
    lang = st.session_state.get("lang", "de")
    st.header(_resolve_text(title, lang=lang))
    if intro is not None:
        st.markdown(_resolve_text(intro, lang=lang))

    st.subheader(tr("Bekannt", "Known", lang=lang))
    known_cb()

    if tools_cb is not None:
        # GREP:TOOLS_EXPANDER_V2
        with st.expander(tr("Tools", "Tools", lang=lang)):
            tools_cb()

    st.subheader(tr("Fehlend", "Missing", lang=lang))
    if missing_paths:
        missing_lines = "\n".join(f"- `{path}`" for path in missing_paths)
        st.markdown(missing_lines)
    else:
        st.info(tr("Keine fehlenden Angaben.", "No missing items.", lang=lang))
    if missing_cb is not None:
        missing_cb()

    st.subheader(tr("Validieren", "Validate", lang=lang))
    if missing_paths:
        st.warning(tr("Kritische Felder sind noch offen.", "Some critical fields are still missing.", lang=lang))
        render_missing_field_summary(missing_paths, scope="step")
    else:
        st.success(tr("Keine kritischen Felder offen.", "No critical fields missing.", lang=lang))
