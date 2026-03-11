"""Helpers for per-field provenance metadata in wizard state."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from constants.keys import StateKeys
from state.ai_contributions import get_profile_metadata

LOW_CONFIDENCE_THRESHOLD = 0.6


FieldMetadataDict = dict[str, Any]


def _ensure_profile_dict() -> dict[str, Any]:
    profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, dict):
        return profile
    if isinstance(profile, Mapping):
        normalized = dict(profile)
    else:
        normalized = {}
    st.session_state[StateKeys.PROFILE] = normalized
    return normalized


def _ensure_field_meta_store(profile: dict[str, Any]) -> dict[str, FieldMetadataDict]:
    meta = profile.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        profile["meta"] = meta
    store = meta.setdefault("field_metadata", {})
    if not isinstance(store, dict):
        store = {}
        meta["field_metadata"] = store
    return store


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"high", "hoch"}:
            return 0.85
        if cleaned in {"medium", "mittel"}:
            return 0.6
        if cleaned in {"low", "niedrig"}:
            return 0.35
        try:
            return max(0.0, min(1.0, float(cleaned)))
        except ValueError:
            return 1.0
    return 1.0


def get_field_metadata(path: str, *, profile: Mapping[str, Any] | None = None) -> FieldMetadataDict | None:
    """Return metadata for ``path`` if present, with legacy fallback hydration."""

    profile_dict = dict(profile) if isinstance(profile, Mapping) else _ensure_profile_dict()
    meta_store = _ensure_field_meta_store(profile_dict)
    existing = meta_store.get(path)
    if isinstance(existing, Mapping):
        return dict(existing)

    canonical_metadata = get_profile_metadata()
    if path in canonical_metadata.evidence:
        confidence_entry = canonical_metadata.confidence.get(path)
        confidence_value = None
        if confidence_entry is not None:
            confidence_value = (
                confidence_entry.score if confidence_entry.score is not None else confidence_entry.confidence
            )
        hydrated: FieldMetadataDict = {
            "source": "heuristic",
            "confidence": _coerce_confidence(confidence_value),
            "evidence_snippet": None,
            "confirmed": False,
        }
        meta_store[path] = hydrated
        st.session_state[StateKeys.PROFILE] = profile_dict
        return hydrated
    return None


def set_field_confirmed(path: str, confirmed: bool) -> None:
    """Persist confirmation state for a field metadata entry."""

    profile = _ensure_profile_dict()
    meta_store = _ensure_field_meta_store(profile)
    current = meta_store.get(path)
    if not isinstance(current, dict):
        current = {
            "source": "heuristic",
            "confidence": 0.5,
            "evidence_snippet": None,
            "confirmed": False,
        }
    current["confirmed"] = bool(confirmed)
    if current["source"] == "user" and confirmed:
        current["confidence"] = 1.0
    meta_store[path] = current
    st.session_state[StateKeys.PROFILE] = profile


def is_unconfirmed_low_confidence_heuristic(path: str, *, profile: Mapping[str, Any] | None = None) -> bool:
    """Return True when field is heuristic and not confirmed with low confidence."""

    metadata = get_field_metadata(path, profile=profile)
    if not metadata:
        return False
    if str(metadata.get("source") or "").lower() != "heuristic":
        return False
    if bool(metadata.get("confirmed", False)):
        return False
    confidence = _coerce_confidence(metadata.get("confidence"))
    return confidence < LOW_CONFIDENCE_THRESHOLD


def list_unconfirmed_heuristic_fields(paths: list[str], *, profile: Mapping[str, Any] | None = None) -> list[str]:
    return [path for path in paths if is_unconfirmed_low_confidence_heuristic(path, profile=profile)]
