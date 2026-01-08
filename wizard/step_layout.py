"""Helpers for standard step layouts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import streamlit as st

from utils.i18n import tr


LocalizedText = tuple[str, str]


def render_step_layout(
    title: LocalizedText,
    intro: LocalizedText | None,
    *,
    known_cb: Callable[[], None],
    missing_paths: Sequence[str] | None = None,
    tools_cb: Callable[[], None] | None = None,
) -> None:
    """Render a standard step layout with Known/Missing tabs and optional tools."""

    # GREP:STEP_LAYOUT_V1
    lang = st.session_state.get("lang", "de")
    st.header(tr(*title, lang=lang))
    if intro is not None:
        st.markdown(tr(*intro, lang=lang))

    known_label = tr("Bekannt", "Known", lang=lang)
    missing_label = tr("Fehlend", "Missing", lang=lang)
    tabs = st.tabs([known_label, missing_label])

    with tabs[0]:
        # GREP:KNOWN_TAB_V1
        known_cb()

    with tabs[1]:
        # GREP:MISSING_TAB_V1
        if missing_paths:
            missing_lines = "\n".join(f"- `{path}`" for path in missing_paths)
            st.markdown(missing_lines)
        else:
            st.info(tr("Keine fehlenden Angaben.", "No missing items.", lang=lang))

    if tools_cb is not None:
        # GREP:TOOLS_EXPANDER_V1
        with st.expander(tr("Tools", "Tools", lang=lang)):
            tools_cb()
