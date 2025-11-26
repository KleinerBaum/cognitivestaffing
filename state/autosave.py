"""Session autosave and import/export helpers for the wizard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from core.schema_migrations import migrate_profile
from utils.i18n import tr


AutosavePayload = dict[str, Any]


def _coerce_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def _normalize_reasoning_mode(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in {"quick", "precise"}:
        return candidate
    if candidate in {"genau", "präzise"}:
        return "precise"
    if candidate in {"schnell", "fast"}:
        return "quick"
    return None


def _sanitize_wizard_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, Mapping):
        return {}
    sanitized: dict[str, Any] = {}
    current_step = state.get("current_step")
    if isinstance(current_step, str):
        sanitized["current_step"] = current_step
    for key in ("completed_steps", "skipped_steps"):
        value = state.get(key)
        if isinstance(value, list):
            sanitized[key] = [str(entry) for entry in value if isinstance(entry, str)]
    return sanitized


def build_snapshot(
    profile_data: Mapping[str, Any] | None,
    *,
    wizard_state: Mapping[str, Any] | None = None,
    lang: str | None = None,
    reasoning_mode: str | None = None,
    step_index: int | None = None,
) -> AutosavePayload:
    """Return a portable snapshot that can be exported or restored later."""

    migrated_profile = migrate_profile(profile_data)
    meta: dict[str, Any] = {"captured_at": datetime.now(timezone.utc).isoformat()}
    if lang := _coerce_str(lang):
        meta["lang"] = lang
    if mode := _normalize_reasoning_mode(reasoning_mode):
        meta["reasoning_mode"] = mode
    if step_index is not None:
        meta["step_index"] = step_index

    snapshot: AutosavePayload = {
        "profile": migrated_profile,
        "wizard": _sanitize_wizard_state(wizard_state),
        "meta": meta,
    }
    return snapshot


def _resolve_snapshot_components(
    payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any] | None, Mapping[str, Any]]:
    profile_data: Mapping[str, Any]
    wizard_data: Mapping[str, Any] | None = None
    meta: Mapping[str, Any] = {}
    if "profile" in payload:
        candidate = payload.get("profile")
        profile_data = candidate if isinstance(candidate, Mapping) else {}
        wizard_raw = payload.get("wizard")
        if isinstance(wizard_raw, Mapping):
            wizard_data = wizard_raw
        meta_raw = payload.get("meta")
        if isinstance(meta_raw, Mapping):
            meta = meta_raw
    else:
        profile_data = payload
    return profile_data, wizard_data, meta


def parse_snapshot(payload: Mapping[str, Any]) -> AutosavePayload:
    """Normalise a snapshot payload from autosave or upload."""

    profile_data, wizard_state, meta = _resolve_snapshot_components(payload)
    return build_snapshot(
        profile_data,
        wizard_state=wizard_state,
        lang=_coerce_str(meta.get("lang") or payload.get("lang")),
        reasoning_mode=_normalize_reasoning_mode(meta.get("reasoning_mode") or payload.get("reasoning_mode")),
        step_index=_coerce_int(meta.get("step_index") or payload.get("step_index")),
    )


def persist_session_snapshot() -> AutosavePayload:
    """Capture the current session into ``StateKeys.AUTOSAVE``."""

    wizard_state = st.session_state.get("wizard")
    snapshot = build_snapshot(
        st.session_state.get(StateKeys.PROFILE),
        wizard_state=wizard_state if isinstance(wizard_state, Mapping) else None,
        lang=st.session_state.get("lang"),
        reasoning_mode=st.session_state.get(StateKeys.REASONING_MODE),
        step_index=_coerce_int(st.session_state.get(StateKeys.STEP)),
    )
    st.session_state[StateKeys.AUTOSAVE] = snapshot
    return snapshot


def apply_snapshot_to_session(snapshot: Mapping[str, Any]) -> AutosavePayload:
    """Apply a snapshot payload to ``st.session_state``."""

    parsed = parse_snapshot(snapshot)
    st.session_state[StateKeys.PROFILE] = parsed["profile"]
    wizard_state = parsed.get("wizard")
    if isinstance(wizard_state, Mapping):
        st.session_state["wizard"] = dict(wizard_state)
    meta = parsed.get("meta", {}) if isinstance(parsed.get("meta"), Mapping) else {}
    lang = _coerce_str(meta.get("lang"))
    if lang:
        st.session_state["lang"] = lang
        st.session_state[UIKeys.LANG_SELECT] = lang
    mode = _normalize_reasoning_mode(meta.get("reasoning_mode"))
    if mode:
        st.session_state[StateKeys.REASONING_MODE] = mode
        st.session_state[UIKeys.REASONING_MODE] = mode
    step_index = _coerce_int(meta.get("step_index"))
    if step_index is not None:
        st.session_state[StateKeys.STEP] = step_index
    st.session_state[StateKeys.AUTOSAVE] = parsed
    return parsed


def serialize_snapshot(snapshot: Mapping[str, Any]) -> bytes:
    """Return a JSON representation of ``snapshot`` for download."""

    return json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")


def maybe_render_autosave_prompt() -> None:
    """Ask the user whether to restore an available autosave payload."""

    snapshot = st.session_state.get(StateKeys.AUTOSAVE)
    if not isinstance(snapshot, Mapping):
        return
    if st.session_state.get(StateKeys.AUTOSAVE_PROMPT_ACK):
        return

    lang = st.session_state.get("lang", "de")
    st.info(
        tr(
            "Eine zwischengespeicherte Sitzung wurde gefunden. Möchtest du sie fortsetzen?",
            "We found an autosaved session. Would you like to continue with it?",
            lang=lang,
        )
    )
    col_restore, col_discard = st.columns(2)
    if col_restore.button(
        tr("🔄 Sitzung fortsetzen", "🔄 Resume session", lang=lang),
        key="autosave.restore",
    ):
        apply_snapshot_to_session(snapshot)
        st.session_state[StateKeys.AUTOSAVE_PROMPT_ACK] = True
        st.toast(tr("Sitzung wiederhergestellt.", "Session restored.", lang=lang), icon="💾")
        st.rerun()

    if col_discard.button(
        tr("🗑️ Verwerfen", "🗑️ Discard", lang=lang),
        key="autosave.discard",
    ):
        st.session_state.pop(StateKeys.AUTOSAVE, None)
        st.session_state[StateKeys.AUTOSAVE_PROMPT_ACK] = True
        st.toast(tr("Zwischenspeicher gelöscht.", "Autosave cleared.", lang=lang), icon="🧹")
        st.rerun()
