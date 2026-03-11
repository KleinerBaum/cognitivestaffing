"""Guardrails for navigation state ownership."""

from __future__ import annotations

import ast
from pathlib import Path

TARGET_KEYS = {"STEP", "WIZARD_LAST_STEP"}
ALLOWLIST = {
    Path("wizard/navigation/router.py"),
    Path("wizard/flow.py"),
    Path("utils/session.py"),
    Path("state/autosave.py"),
    Path("ui_views/advantages.py"),
}
SKIP_PARTS = {".git", ".venv", "__pycache__", "tests"}


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        files.append(rel)
    return files


def _is_navigation_key_write(node: ast.Assign | ast.AnnAssign) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if not isinstance(target, ast.Subscript):
            continue
        index = target.slice
        if isinstance(index, ast.Attribute) and isinstance(index.value, ast.Name):
            if index.value.id == "StateKeys" and index.attr in TARGET_KEYS:
                return True
    return False


def test_navigation_state_writes_owned_by_controller() -> None:
    root = Path(__file__).resolve().parents[2]
    violations: list[str] = []
    for rel_path in _iter_python_files(root):
        if rel_path in ALLOWLIST:
            continue
        source = (root / rel_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_navigation_key_write(node):
                line = getattr(node, "lineno", 1)
                violations.append(f"{rel_path}:{line}")
    assert not violations, "Direct writes to StateKeys.STEP/WIZARD_LAST_STEP outside controller: " + ", ".join(
        violations
    )
