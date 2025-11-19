"""Utility helpers for rendering error messages in Streamlit."""

from __future__ import annotations

from typing import Final

import streamlit as st

from utils.i18n import tr
from utils.admin_debug import is_admin_debug_session_active

LocalizedMessage = str | tuple[str, str]
_DETAILS_LABEL: Final[tuple[str, str]] = (
    "Details",
    "Details",
)


def resolve_message(message: LocalizedMessage, *, lang: str | None = None) -> str:
    """Return the localized string for ``message``.

    Args:
        message: Either a plain string or a ``(de, en)`` tuple.
        lang: Optional language override.
    """

    if isinstance(message, tuple):
        de, en = message
        return tr(de, en, lang=lang)
    return message


def display_error(
    msg: LocalizedMessage,
    detail: str | None = None,
    *,
    lang: str | None = None,
) -> None:
    """Render a user-facing error with optional debug details.

    Args:
        msg: Short error message for the user.
        detail: Optional technical detail shown when debug mode is enabled.
        lang: Optional language override for the main message.
    """

    text = resolve_message(msg, lang=lang)
    st.error(text)
    if detail and is_admin_debug_session_active():
        with st.expander(resolve_message(_DETAILS_LABEL, lang=lang)):
            st.code(detail)
