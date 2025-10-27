"""Tests for the canonical alias mapping and key registry."""

from __future__ import annotations

from collections.abc import Mapping

from core.schema import ALIASES, ALL_FIELDS, KEYS_CANONICAL, canonicalize_profile_payload


def _set_path(payload: dict[str, object], path: str, value: object) -> None:
    parts = path.split(".")
    cursor: dict[str, object] = payload
    for part in parts[:-1]:
        next_value = cursor.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise AssertionError(f"Intermediate path '{part}' is not a dict for alias '{path}'")
        cursor = next_value  # type: ignore[assignment]
    cursor[parts[-1]] = value


def _get_path(payload: Mapping[str, object], path: str) -> object | None:
    cursor: object = payload
    for part in path.split("."):
        if not isinstance(cursor, Mapping):
            return None
        if part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def test_alias_mapping_complete() -> None:
    """Ensure aliases map to canonical keys and are applied during canonicalisation."""

    assert set(KEYS_CANONICAL) == set(ALL_FIELDS)

    for alias, target in ALIASES.items():
        assert target in KEYS_CANONICAL, f"Alias target '{target}' is not canonical"

        sentinel = f"alias:{alias}"
        payload: dict[str, object] = {}
        _set_path(payload, alias, sentinel)
        canonical = canonicalize_profile_payload(payload)

        if target.startswith(f"{alias}."):
            alias_container = _get_path(canonical, alias)
            assert isinstance(alias_container, Mapping), f"Alias '{alias}' did not produce mapping for '{target}'"
        else:
            assert _get_path(canonical, alias) is None, f"Alias '{alias}' leaked into canonical payload"
        canonical_value = _get_path(canonical, target)
        assert canonical_value not in (None, {}), f"Alias '{alias}' not applied to canonical target '{target}'"
        if isinstance(canonical_value, list):
            assert canonical_value, f"Alias '{alias}' produced empty list for '{target}'"
        else:
            assert canonical_value == sentinel, f"Alias '{alias}' value changed unexpectedly for '{target}'"
