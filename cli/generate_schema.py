"""Utilities for regenerating persisted JSON schema files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.schema import build_need_analysis_responses_schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "need_analysis.schema.json"


def generate_need_analysis_schema() -> dict[str, Any]:
    """Return the Need Analysis JSON schema used for Responses outputs."""

    return build_need_analysis_responses_schema()


def write_need_analysis_schema(path: Path = SCHEMA_PATH) -> None:
    """Regenerate the persisted schema file on disk."""

    schema = generate_need_analysis_schema()
    path.write_text(json.dumps(schema, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    write_need_analysis_schema()
