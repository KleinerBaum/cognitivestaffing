"""Helpers for tracking AI step failures and skip decisions."""

from __future__ import annotations

from typing import MutableMapping

import streamlit as st

from constants.keys import StateKeys

AI_FAILURE_THRESHOLD: int = 2


def _coerce_failure_state() -> tuple[MutableMapping[str, int], set[str]]:
    failures_raw = st.session_state.get(StateKeys.STEP_FAILURES, {})
    skipped_raw = st.session_state.get(StateKeys.STEP_AI_SKIPPED, [])

    failures: MutableMapping[str, int]
    if isinstance(failures_raw, MutableMapping):
        normalized: dict[str, int] = {}
        for key, value in failures_raw.items():
            try:
                normalized[str(key)] = int(value)
            except (TypeError, ValueError):
                normalized[str(key)] = 0
        failures = normalized
    else:
        failures = {}

    skipped: set[str] = set()
    if isinstance(skipped_raw, (list, set, tuple)):
        for entry in skipped_raw:
            if isinstance(entry, str) and entry:
                skipped.add(entry)
            elif entry is not None:
                skipped.add(str(entry))

    st.session_state[StateKeys.STEP_FAILURES] = failures
    st.session_state[StateKeys.STEP_AI_SKIPPED] = list(skipped)
    return failures, skipped


def get_failure_count(step_key: str) -> int:
    failures, _ = _coerce_failure_state()
    return int(failures.get(step_key, 0))


def increment_step_failure(step_key: str) -> int:
    failures, _ = _coerce_failure_state()
    failures[step_key] = failures.get(step_key, 0) + 1
    st.session_state[StateKeys.STEP_FAILURES] = failures
    return failures[step_key]


def reset_step_failures(step_key: str) -> None:
    failures, _ = _coerce_failure_state()
    if step_key in failures:
        failures[step_key] = 0
        st.session_state[StateKeys.STEP_FAILURES] = failures


def mark_step_ai_skipped(step_key: str) -> None:
    failures, skipped = _coerce_failure_state()
    failures[step_key] = 0
    skipped.add(step_key)
    st.session_state[StateKeys.STEP_FAILURES] = failures
    st.session_state[StateKeys.STEP_AI_SKIPPED] = list(skipped)


def is_step_ai_skipped(step_key: str) -> bool:
    _, skipped = _coerce_failure_state()
    return step_key in skipped


def get_skipped_steps() -> set[str]:
    _, skipped = _coerce_failure_state()
    return set(skipped)


def should_offer_skip(step_key: str, *, threshold: int = AI_FAILURE_THRESHOLD) -> bool:
    if is_step_ai_skipped(step_key):
        return False
    return get_failure_count(step_key) >= threshold
