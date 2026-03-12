"""Contract tests ensuring wizard field paths stay on canonical ProfilePaths values."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Final

from constants.keys import ProfilePaths
from wizard.metadata import PAGE_PROGRESS_FIELDS
from wizard.step_registry import WIZARD_STEPS


ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FIELD_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z_]+(?:\.[a-z0-9_]+)+$")
LEGACY_PROFILE_PATH_ALIASES: Final[set[str]] = {
    "summary.headline",
    "summary.value_proposition",
    "summary.culture_highlights",
    "summary.next_steps",
}
PROFILE_PATH_ROOTS: Final[set[str]] = {path.split(".", 1)[0] for path in ProfilePaths.all_values()}
PYTHON_SOURCES: Final[tuple[Path, ...]] = (
    ROOT / "question_logic.py",
    ROOT / "wizard" / "step_registry.py",
    ROOT / "wizard" / "metadata.py",
)


def _collect_role_field_map_paths() -> set[str]:
    payload = json.loads((ROOT / "role_field_map.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    paths: set[str] = set()
    for fields in payload.values():
        if not isinstance(fields, list):
            continue
        for field in fields:
            if isinstance(field, str) and FIELD_PATH_PATTERN.match(field):
                paths.add(field)
    return paths


def _collect_critical_field_paths() -> set[str]:
    payload = json.loads((ROOT / "critical_fields.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    raw = payload.get("critical", [])
    assert isinstance(raw, list)
    return {field for field in raw if isinstance(field, str) and FIELD_PATH_PATTERN.match(field)}


def _collect_python_literal_paths(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if FIELD_PATH_PATTERN.match(node.value) and not node.value.endswith("_"):
                root = node.value.split(".", 1)[0]
                if root in PROFILE_PATH_ROOTS or node.value in LEGACY_PROFILE_PATH_ALIASES:
                    paths.add(node.value)
    return paths


def test_step_registry_required_and_summary_fields_are_canonical() -> None:
    allowed = ProfilePaths.all_values() | LEGACY_PROFILE_PATH_ALIASES

    for step in WIZARD_STEPS:
        for field in (*step.required_fields, *step.summary_fields):
            assert field in allowed, f"{step.key} uses non-canonical field path: {field}"


def test_metadata_page_progress_fields_are_canonical() -> None:
    allowed = ProfilePaths.all_values() | LEGACY_PROFILE_PATH_ALIASES

    for page_key, fields in PAGE_PROGRESS_FIELDS.items():
        for field in fields:
            if field.startswith("__page__."):
                continue
            assert field in allowed, f"{page_key} uses non-canonical progress field path: {field}"


def test_profile_paths_cover_json_and_python_path_references() -> None:
    allowed = ProfilePaths.all_values() | LEGACY_PROFILE_PATH_ALIASES

    referenced_paths = set()
    referenced_paths.update(_collect_role_field_map_paths())
    referenced_paths.update(_collect_critical_field_paths())
    for source_path in PYTHON_SOURCES:
        referenced_paths.update(_collect_python_literal_paths(source_path))

    unknown_paths = sorted(path for path in referenced_paths if path not in allowed)
    assert not unknown_paths, f"Unknown field paths not in ProfilePaths: {unknown_paths}"
