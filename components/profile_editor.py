from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

import streamlit as st

from utils.i18n import tr

# GREP:PROFILE_EDITOR_V1


@dataclass(frozen=True)
class ProfileEditorField:
    """Describe a profile field rendered by the profile editor."""

    path: str
    label: tuple[str, str]
    help_text: tuple[str, str] | None = None
    placeholder: tuple[str, str] | None = None
    widget: Literal["text", "textarea"] = "text"


def safe_get_in(data: Mapping[str, Any] | None, path: str, default: Any = "") -> Any:
    """Return a nested value from a dotted ``path`` when available."""

    if not data:
        return default
    cursor: Any = data
    for part in path.split("."):
        if isinstance(cursor, Mapping) and part in cursor:
            cursor = cursor[part]
        else:
            return default
    return cursor


def safe_set_in(data: dict[str, Any], path: str, value: Any) -> None:
    """Set ``value`` inside ``data`` following a dotted ``path`` safely."""

    if not path:
        return
    cursor = data
    parts = path.split(".")
    for part in parts[:-1]:
        next_cursor = cursor.get(part)
        if not isinstance(next_cursor, dict):
            next_cursor = {}
            cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def render_profile_editor(
    *,
    profile: dict[str, Any],
    fields: Sequence[ProfileEditorField],
    key_prefix: str,
    lang: str | None = None,
) -> None:
    """Render editable fields and persist updates into ``profile``."""

    active_lang = (lang or st.session_state.get("lang", "de"))[:2]
    for field in fields:
        label = tr(*field.label, lang=active_lang)
        help_text = tr(*field.help_text, lang=active_lang) if field.help_text else None
        placeholder = tr(*field.placeholder, lang=active_lang) if field.placeholder else None
        key = f"{key_prefix}.{field.path}"
        value = _stringify(safe_get_in(profile, field.path, ""))
        if field.widget == "textarea":
            updated = st.text_area(
                label,
                value=value,
                key=key,
                help=help_text,
                placeholder=placeholder,
            )
        else:
            updated = st.text_input(
                label,
                value=value,
                key=key,
                help=help_text,
                placeholder=placeholder,
            )
        if updated != value:
            safe_set_in(profile, field.path, updated)
