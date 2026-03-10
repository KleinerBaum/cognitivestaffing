"""Shared helpers for Wizard V2 step stubs."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from constants.keys import StateKeys
from utils.i18n import tr
from wizard.navigation_types import WizardContext
from wizard.step_layout import render_step_layout


LocalizedPair = tuple[str, str]


def render_v2_step(
    context: WizardContext,
    *,
    title: LocalizedPair,
    intro: LocalizedPair,
    missing_paths: Sequence[str],
    known_fields: Sequence[tuple[str, str]],
) -> None:
    """Render a V2 step using the canonical Known/Missing/Validate layout."""

    profile = st.session_state.get(StateKeys.PROFILE, {})
    data = profile if isinstance(profile, dict) else {}

    def _known() -> None:
        if not known_fields:
            st.caption(tr("Noch keine Daten vorhanden.", "No captured data yet."))
            return
        for label_path, field_path in known_fields:
            parent: object = data
            for part in field_path.split("."):
                if isinstance(parent, dict):
                    parent = parent.get(part)
                else:
                    parent = None
                    break
            value = parent
            pretty = value if value not in (None, "", [], {}) else tr("Nicht gesetzt", "Not set")
            st.markdown(f"- **{label_path}**: `{pretty}`")

    def _missing() -> None:
        st.caption(
            tr(
                "Ergänze nur die fehlenden Informationen für diesen Schritt.",
                "Add only the missing information for this step.",
            )
        )

    render_step_layout(
        title,
        intro,
        known_cb=_known,
        missing_cb=_missing,
        missing_paths=missing_paths,
    )
