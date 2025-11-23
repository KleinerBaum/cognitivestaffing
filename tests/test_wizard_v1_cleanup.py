"""Guards against reintroducing deprecated Wizard v1 scaffolding."""

from __future__ import annotations

from pathlib import Path


BANNED_PATTERNS: tuple[str, ...] = (
    "wizard_state['feature']",
    'wizard_state["feature"]',
    "coerce_and_fill_wizard",
)


def test_no_legacy_wizard_v1_strings() -> None:
    """Ensure the codebase no longer references the Wizard v1 helpers."""

    repo_root = Path(__file__).resolve().parents[1]
    current_file = Path(__file__).resolve()
    offenders: list[str] = []

    for py_file in repo_root.rglob("*.py"):
        if py_file == current_file:
            continue
        contents = py_file.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            if pattern in contents:
                relative_path = py_file.relative_to(repo_root)
                offenders.append(f"{relative_path}:{pattern}")

    assert not offenders, "Deprecated Wizard v1 references linger in the codebase: " + ", ".join(offenders)
