from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Sequence

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
    formatter: Callable[[Any], str] | None = None
    parser: Callable[[str], Any] | None = None


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


def format_list(value: Any) -> str:
    """Return a list-like value as newline-delimited text."""

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(items)
    return _stringify(value)


def parse_list(value: str) -> list[str]:
    """Parse comma or newline separated text into a list."""

    if not value:
        return []
    items = [item.strip() for chunk in value.splitlines() for item in chunk.split(",")]
    return [item for item in items if item]


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
        raw_value = safe_get_in(profile, field.path, "")
        value = field.formatter(raw_value) if field.formatter else _stringify(raw_value)
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
            parsed = field.parser(updated) if field.parser else updated
            safe_set_in(profile, field.path, parsed)
