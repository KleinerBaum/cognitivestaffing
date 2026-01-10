from __future__ import annotations

from pathlib import Path


def load_text(name: str) -> str:
    """Load a job ad fixture by filename."""
    fixture_path = Path(__file__).parent / name
    return fixture_path.read_text(encoding="utf-8")
