"""Helpers for standard step layouts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import streamlit as st

from constants.keys import StateKeys
from utils.i18n import tr
from wizard import metadata as wizard_metadata
from wizard.field_metadata import get_field_metadata, set_field_confirmed
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
    _render_heuristic_review(lang=lang, step_key=st.session_state.get(StateKeys.WIZARD_LAST_STEP))
    if missing_paths:
        st.warning(tr("Kritische Felder sind noch offen.", "Some critical fields are still missing.", lang=lang))
        render_missing_field_summary(missing_paths, scope="step")
    else:
        st.success(tr("Keine kritischen Felder offen.", "No critical fields missing.", lang=lang))


def _render_heuristic_review(*, lang: str, step_key: str | None) -> None:
    if not step_key:
        return
    profile = st.session_state.get(StateKeys.PROFILE, {}) or {}
    step_fields = wizard_metadata.PAGE_PROGRESS_FIELDS.get(step_key, ())
    heuristic_fields: list[str] = []
    for field_path in step_fields:
        metadata = get_field_metadata(field_path, profile=profile if isinstance(profile, dict) else None)
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("source") or "").lower() != "heuristic":
            continue
        heuristic_fields.append(field_path)

    if not heuristic_fields:
        return

    st.caption(tr("⚡ Vorgeschlagene Werte prüfen", "⚡ Review suggested values", lang=lang))
    for field_path in heuristic_fields:
        metadata = get_field_metadata(field_path, profile=profile if isinstance(profile, dict) else None) or {}
        confidence = float(metadata.get("confidence") or 0.0)
        current_value = profile
        for part in field_path.split("."):
            if isinstance(current_value, dict):
                current_value = current_value.get(part)
            else:
                current_value = None
                break
        badge = tr("Vorgeschlagen", "Suggested", lang=lang)
        st.markdown(f"- **`{field_path}`** · 🏷️ {badge} · {tr('Konfidenz', 'Confidence', lang=lang)}: {confidence:.0%}")
        confirmed = st.checkbox(
            tr("Wert bestätigt", "Confirm value", lang=lang),
            value=bool(metadata.get("confirmed", False)),
            key=f"confirm.{step_key}.{field_path}",
        )
        if confirmed != bool(metadata.get("confirmed", False)):
            set_field_confirmed(field_path, confirmed)
        if metadata.get("evidence_snippet"):
            st.caption(str(metadata["evidence_snippet"]))
        if current_value not in (None, "", [], {}):
            st.caption(f"{tr('Aktueller Wert', 'Current value', lang=lang)}: {current_value}")
