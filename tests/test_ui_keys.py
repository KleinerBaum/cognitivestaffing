"""Regression tests guarding UI key uniqueness.

UNIQUE_UI_KEYS
"""

from constants.keys import UIKeys


def test_no_duplicate_ui_keys() -> None:
    """Ensure Streamlit widget keys remain unique across UIKeys."""

    value_to_names: dict[str, list[str]] = {}
    for name, value in vars(UIKeys).items():
        if name.startswith("_") or not isinstance(value, str):
            continue
        value_to_names.setdefault(value, []).append(name)

    duplicates = {value: names for value, names in value_to_names.items() if len(names) > 1}
    assert not duplicates, f"Duplicate UI keys detected: {duplicates}"
