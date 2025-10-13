"""Streamlit friendly ESCO integration wrapper.

The original HTTP based client is replaced with a deterministic wrapper
around :mod:`core.esco_utils`.  This keeps the UI responsive in offline
environments while exposing the same session state side effects used by the
wizard.
"""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from constants.keys import StateKeys, UIKeys
from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    search_occupations,
)


def _set_state(key: str, value) -> None:
    """Helper that writes to ``st.session_state`` when available."""

    try:
        st.session_state[key] = value
    except Exception:  # pragma: no cover - streamlit safety belt
        pass


def search_occupation(title: str, lang: str = "en") -> Dict[str, str]:
    """Return the best matching occupation for ``title`` and store metadata."""

    occupation = classify_occupation(title, lang=lang) or {}
    options = search_occupations(title, lang=lang, limit=5) if occupation else []
    _set_state(StateKeys.ESCO_OCCUPATION_OPTIONS, options)
    if occupation:
        skills = get_essential_skills(occupation.get("uri", ""), lang=lang)
        _set_state(StateKeys.ESCO_SKILLS, skills)
        _set_state(StateKeys.ESCO_SELECTED_OCCUPATIONS, [occupation])
        _set_state(UIKeys.POSITION_ESCO_OCCUPATION, [occupation.get("uri", "")])
    else:
        _set_state(StateKeys.ESCO_SKILLS, [])
        _set_state(StateKeys.ESCO_SELECTED_OCCUPATIONS, [])
        _set_state(UIKeys.POSITION_ESCO_OCCUPATION, [])
    return occupation


def search_occupation_options(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return occupation candidates for ``title`` and update session state."""

    options = search_occupations(title, lang=lang, limit=limit)
    _set_state(StateKeys.ESCO_OCCUPATION_OPTIONS, options)
    return options


def enrich_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return cached essential skills for ``occupation_uri``."""

    skills = get_essential_skills(occupation_uri, lang=lang)
    _set_state(StateKeys.ESCO_SKILLS, skills)
    return skills
