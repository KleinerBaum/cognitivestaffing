"""Typed helpers for the test-suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NotRequired, Sequence, TypedDict

import streamlit as st

from constants.keys import StateKeys


class FollowupEntry(TypedDict, total=False):
    """Structure describing an inline follow-up question."""

    field: str
    question: str
    priority: NotRequired[str]


class ProfileMeta(TypedDict, total=False):
    """Subset of profile metadata tracked throughout tests."""

    followups_answered: list[str]


class ProfileDict(TypedDict, total=False):
    """Minimal profile payload shared across wizard helpers."""

    meta: ProfileMeta
    company: dict[str, Any]
    compensation: dict[str, Any]


@dataclass(slots=True)
class SessionBootstrap:
    """Utility dataclass to seed ``st.session_state`` with typed values."""

    lang: str = "en"
    followups: Sequence[FollowupEntry] = field(default_factory=tuple)
    rag_context_skipped: bool = False

    def apply(self) -> None:
        """Apply the configuration to ``st.session_state``."""

        st.session_state.clear()
        st.session_state["lang"] = self.lang
        st.session_state[StateKeys.FOLLOWUPS] = list(self.followups)
        if self.rag_context_skipped:
            st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = True


def empty_profile() -> ProfileDict:
    """Return a deep-ish copy of the base profile payload."""

    return {"meta": {"followups_answered": []}}


def make_followup(field: str, question: str, *, priority: str | None = None) -> FollowupEntry:
    """Create a follow-up entry while keeping the type checker happy."""

    entry: FollowupEntry = {"field": field, "question": question}
    if priority is not None:
        entry["priority"] = priority
    return entry


__all__ = [
    "FollowupEntry",
    "ProfileDict",
    "SessionBootstrap",
    "empty_profile",
    "make_followup",
]
