"""Tests for the canonical alias mapping and key registry."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from constants.keys import ProfilePaths
from core.schema import ALIASES, ALL_FIELDS, KEYS_CANONICAL, canonicalize_profile_payload
from models.need_analysis import NeedAnalysisProfile
from pages import WIZARD_PAGES


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


def _flatten_paths(data: object, prefix: str = "") -> Iterable[str]:
    if isinstance(data, Mapping):
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, Mapping):
                yield from _flatten_paths(value, next_prefix)
            else:
                yield next_prefix
    else:
        if prefix:
            yield prefix


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


def test_profile_paths_cover_schema_and_ui() -> None:
    profile_dump = NeedAnalysisProfile().model_dump()
    dump_paths = set(_flatten_paths(profile_dump))
    canonical_paths = set(KEYS_CANONICAL)
    assert dump_paths == canonical_paths

    enum_paths = {member.value for member in ProfilePaths}
    assert enum_paths == canonical_paths

    wizard_paths: set[str] = set()
    for page in WIZARD_PAGES:
        wizard_paths.update(str(field) for field in page.required_fields)
        wizard_paths.update(str(field) for field in page.summary_fields)

    missing = canonical_paths - wizard_paths
    assert not missing, f"Wizard pages missing coverage for: {sorted(missing)}"

    stray = wizard_paths - canonical_paths
    assert not stray, f"Wizard pages reference non-canonical paths: {sorted(stray)}"
