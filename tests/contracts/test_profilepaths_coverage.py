"""Contract test ensuring configured field paths map to ProfilePaths canonicals."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Final

from constants.keys import ProfilePaths


ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FIELD_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z_]+(?:\.[a-z0-9_]+)+$")
PROFILE_PATH_ROOTS: Final[set[str]] = {path.split(".", 1)[0] for path in ProfilePaths.all_values()}
PYTHON_SOURCES: Final[tuple[Path, ...]] = (ROOT / "question_logic.py",)


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
            if FIELD_PATH_PATTERN.match(node.value) and node.value.split(".", 1)[0] in PROFILE_PATH_ROOTS:
                paths.add(node.value)
    return paths


def test_profile_paths_cover_json_and_python_path_references() -> None:
    allowed = ProfilePaths.all_values()

    referenced_paths = set()
    referenced_paths.update(_collect_role_field_map_paths())
    referenced_paths.update(_collect_critical_field_paths())
    for source_path in PYTHON_SOURCES:
        referenced_paths.update(_collect_python_literal_paths(source_path))

    unknown_paths = sorted(path for path in referenced_paths if path not in allowed)
    assert not unknown_paths, f"Unknown field paths not in ProfilePaths: {unknown_paths}"
