"""Reusable chip-based multiselect widgets for the wizard UI."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal

import streamlit as st

from utils.i18n import tr
from wizard._logic import unique_normalized

__all__ = [
    "CHIP_INLINE_VALUE_LIMIT",
    "chip_multiselect",
    "chip_multiselect_mapped",
    "group_chip_options_by_label",
    "render_chip_button_grid",
]

CHIP_INLINE_VALUE_LIMIT = 20


def _compact_inline_label(raw: str, *, limit: int = CHIP_INLINE_VALUE_LIMIT) -> tuple[str, bool]:
    """Return a single-line label truncated to ``limit`` characters when needed."""

    text = " ".join(str(raw).split())
    if len(text) <= limit:
        return text, False
    clipped = text[: max(0, limit - 1)].rstrip()
    return f"{clipped}…", True


def _slugify_label(label: str) -> str:
    """Convert a widget label into a slug suitable for state keys."""

    import re  # Local import to avoid polluting module namespace.

    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").lower()
    return cleaned or "field"


def render_chip_button_grid(
    options: Sequence[str],
    *,
    key_prefix: str,
    button_type: Literal["primary", "secondary"] = "secondary",
    columns: int = 3,
    widget_factory: Callable[..., Any] | None = None,
) -> int | None:
    """Render a responsive grid of clickable buttons representing chip choices."""

    if not options:
        return None

    per_row = max(1, min(columns, len(options)))
    grid_columns = st.columns(per_row)
    clicked_index: int | None = None

    button_renderer: Callable[..., Any]
    if widget_factory is not None:
        button_renderer = widget_factory
    else:
        button_renderer = st.button

    for idx, option in enumerate(options):
        option_text = str(option)
        display_text, was_truncated = _compact_inline_label(option_text)
        if idx and idx % per_row == 0:
            remaining = len(options) - idx
            per_row = max(1, min(columns, remaining))
            grid_columns = st.columns(per_row)
        col = grid_columns[idx % per_row]
        with col:
            pressed = button_renderer(
                display_text,
                key=f"{key_prefix}.{idx}",
                type=button_type,
                use_container_width=True,
                help=option_text if was_truncated else None,
            )
        if pressed and clicked_index is None:
            clicked_index = idx

    return clicked_index


def group_chip_options_by_label(entries: Iterable[tuple[str, str, str]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Group chip entries by their translated label while preserving order."""

    grouped: dict[str, list[tuple[str, str]]] = {}
    for group_key, value, label in entries:
        grouped.setdefault(label, []).append((group_key, value))
    return [(label, values) for label, values in grouped.items()]


def chip_multiselect(
    label: str,
    options: Sequence[str],
    values: Sequence[str],
    *,
    key_suffix: str | None = None,
    help_text: str | None = None,
    dropdown: bool = False,
) -> list[str]:
    """Render an interactive chip-based multiselect with free-text additions."""

    slug_parts = [_slugify_label(label)]
    if key_suffix:
        slug_parts.append(_slugify_label(str(key_suffix)))
    slug = ".".join(slug_parts)
    ms_key = f"ms_{slug}"
    options_key = f"ui.chip_options.{slug}"
    input_key = f"ui.chip_input.{slug}"
    last_added_key = f"ui.chip_last_added.{slug}"
    clear_flag_key = f"{input_key}.__clear"

    base_options = unique_normalized(list(options))
    base_values = unique_normalized(list(values))

    stored_options = unique_normalized(st.session_state.get(options_key, []))
    available_options = unique_normalized(stored_options + base_options + base_values)
    available_options = sorted(available_options, key=str.casefold)
    st.session_state[options_key] = available_options

    if ms_key not in st.session_state:
        st.session_state[ms_key] = base_values

    current_values = unique_normalized(st.session_state.get(ms_key, []))

    if st.session_state.get(clear_flag_key):
        st.session_state[input_key] = ""
        st.session_state.pop(clear_flag_key, None)

    def _add_chip_entry() -> None:
        raw_value = st.session_state.get(input_key, "")
        candidate = raw_value.strip() if isinstance(raw_value, str) else ""

        if not candidate:
            st.session_state[input_key] = ""
            st.session_state[last_added_key] = ""
            return

        last_added = st.session_state.get(last_added_key, "")
        current_markers = {item.casefold() for item in current_values}
        candidate_marker = candidate.casefold()

        if candidate_marker in current_markers and candidate_marker == str(last_added).casefold():
            st.session_state[input_key] = ""
            return

        updated_options = sorted(
            unique_normalized(st.session_state.get(options_key, []) + [candidate]),
            key=str.casefold,
        )
        updated_values = unique_normalized(current_values + [candidate])

        st.session_state[options_key] = updated_options
        st.session_state[ms_key] = updated_values
        st.session_state[last_added_key] = candidate
        st.session_state[input_key] = ""
        st.rerun()

    container = st.expander(label, expanded=True) if dropdown else st.container()
    with container:
        if not dropdown:
            st.markdown(f"**{label}**")
        if help_text:
            st.caption(help_text)

        selected_values = unique_normalized(st.session_state.get(ms_key, []))
        available_pool = [
            option
            for option in available_options
            if option.casefold() not in {value.casefold() for value in selected_values}
        ]

        input_placeholder = tr(
            "Weitere Einträge hinzufügen…",
            "Add more entries…",
        )
        st.text_input(
            input_placeholder,
            key=input_key,
            placeholder=input_placeholder,
            on_change=_add_chip_entry,
        )

        if selected_values:
            st.write(tr("Ausgewählt:", "Selected:"))
            clicked_selected = render_chip_button_grid(
                selected_values,
                key_prefix=f"{input_key}.selected",
                button_type="primary",
            )
            if clicked_selected is not None:
                removed_value = selected_values[clicked_selected]
                st.session_state[ms_key] = [
                    value for value in selected_values if value.casefold() != removed_value.casefold()
                ]
                st.session_state[last_added_key] = removed_value
                st.session_state[clear_flag_key] = True
                st.rerun()
        if available_pool:
            st.write(tr("Vorschläge:", "Suggestions:"))
            clicked_available = render_chip_button_grid(
                available_pool,
                key_prefix=f"{input_key}.available",
            )
            if clicked_available is not None:
                value = available_pool[clicked_available]
                updated = unique_normalized(selected_values + [value])
                st.session_state[ms_key] = updated
                st.session_state[last_added_key] = value
                st.session_state[clear_flag_key] = True
                st.rerun()
        elif not selected_values:
            st.caption(tr("Keine Vorschläge verfügbar.", "No suggestions available."))

    return unique_normalized(st.session_state.get(ms_key, []))


def chip_multiselect_mapped(
    label: str,
    option_pairs: Sequence[tuple[str, str]],
    values: Sequence[str],
    *,
    help_text: str | None = None,
    dropdown: bool = False,
    key_suffix: str | None = None,
) -> list[str]:
    """Render a chip multiselect while mapping display labels to stored values."""

    normalized_map: dict[str, str] = {}
    display_options: list[str] = []
    selected_display: list[str] = []

    def _register_option(value: str, display: str, preselect: bool = False) -> None:
        cleaned_display = display.strip()
        if not cleaned_display:
            cleaned_display = value.strip()
        if not cleaned_display:
            return
        candidate = cleaned_display
        suffix = 2
        while candidate.casefold() in normalized_map:
            candidate = f"{cleaned_display} ({suffix})"
            suffix += 1
        normalized_map[candidate.casefold()] = value
        display_options.append(candidate)
        if preselect:
            selected_display.append(candidate)

    for raw_value, display in option_pairs:
        value = str(raw_value)
        display_text = str(display)
        preselect = any(value == str(existing) for existing in values)
        _register_option(value, display_text, preselect=preselect)

    existing_markers = {str(item) for item in normalized_map.values()}
    for raw_value in values:
        value = str(raw_value)
        if value in existing_markers:
            continue
        _register_option(value, value, preselect=True)

    chosen_displays = chip_multiselect(
        label,
        options=display_options,
        values=selected_display,
        key_suffix=key_suffix,
        help_text=help_text,
        dropdown=dropdown,
    )

    result: list[str] = []
    for display in chosen_displays:
        marker = display.casefold()
        if marker in normalized_map:
            result.append(normalized_map[marker])
    return result
