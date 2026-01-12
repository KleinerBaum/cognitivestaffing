"""Schema integrity checks for JSON schema required rules."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SchemaNode = Mapping[str, Any]


def _collect_required_issues(node: Any, *, path: str = "$") -> list[str]:
    issues: list[str] = []
    if isinstance(node, Mapping):
        if node.get("type") == "object":
            required = node.get("required")
            if not isinstance(required, list):
                issues.append(f"{path}: missing required list")
            else:
                properties = node.get("properties")
                if isinstance(properties, Mapping):
                    property_keys = set(properties)
                    required_keys = set(required)
                    if property_keys != required_keys:
                        missing = sorted(property_keys - required_keys)
                        extra = sorted(required_keys - property_keys)
                        detail = ", ".join(
                            chunk
                            for chunk in [
                                f"missing required: {', '.join(missing)}" if missing else "",
                                f"unknown required: {', '.join(extra)}" if extra else "",
                            ]
                            if chunk
                        )
                        issues.append(f"{path}: {detail}")
                elif required:
                    issues.append(f"{path}: required must be empty when properties are absent")

        for key, value in node.items():
            if isinstance(value, (Mapping, list)):
                issues.extend(_collect_required_issues(value, path=f"{path}.{key}"))

    elif isinstance(node, list):
        for index, item in enumerate(node):
            issues.extend(_collect_required_issues(item, path=f"{path}[{index}]"))

    return issues


def test_need_analysis_schema_required_integrity() -> None:
    """Ensure object schemas define required arrays compatible with Responses."""

    schema_path = Path("schema/need_analysis.schema.json")
    schema: SchemaNode = json.loads(schema_path.read_text(encoding="utf-8"))

    issues = _collect_required_issues(schema)

    assert not issues, "Schema required integrity issues found:\n" + "\n".join(issues)
