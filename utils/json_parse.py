"""
Robust JSON parsing utilities for LLM extraction output.

Implements:
- CS-PAR-01: Strict parser with sanitization
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from models.need_analysis import NeedAnalysisProfile
from core.schema import (
    ALIASES,
    ALL_FIELDS,
    BOOL_FIELDS,
    FLOAT_FIELDS,
    INT_FIELDS,
    LIST_FIELDS,
)


_CODE_FENCE_RE = re.compile(
    r"^```[a-zA-Z0-9_+-]*\s*$|^```\s*$|^\uFEFF|^\ufeff",  # fences or BOM at line start
    flags=re.MULTILINE,
)


def _strip_code_fences(s: str) -> str:
    """
    Remove Markdown code-fence lines and BOMs that can confuse JSON parsers.
    Leaves the body intact.
    """
    if not s:
        return s
    # Remove leading BOMs
    s = s.lstrip("\ufeff").lstrip("\ufeff")
    # Drop fence lines like ``` or ```json
    return _CODE_FENCE_RE.sub("", s)


def _first_balanced_json(s: str) -> Optional[str]:
    """
    Return the first balanced {...} JSON object from the string, or None.

    Handles braces inside quoted strings and escape sequences.
    """
    if not s:
        return None

    in_str = False
    esc = False
    depth = 0
    start = -1

    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        # not in string
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    return s[start : i + 1]  # noqa: E203
    return None


def _find_key_ci(d: dict[str, Any], key: str) -> Optional[str]:
    """Return the actual dict key matching ``key`` case-insensitively."""

    key_lower = key.lower()
    for k in d.keys():
        if k.lower() == key_lower:
            return k
    return None


def _apply_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Map alias keys in ``data`` to schema paths."""

    for alias, target in ALIASES.items():
        src_parts = alias.split(".")
        cursor = data
        parents: list[dict[str, Any]] = []
        keys: list[str] = []
        for part in src_parts:
            if not isinstance(cursor, dict):
                break
            actual = _find_key_ci(cursor, part)
            if actual is None:
                break
            parents.append(cursor)
            keys.append(actual)
            cursor = cursor[actual]
        else:
            value = cursor
            parent = parents[-1]
            del parent[keys[-1]]
            tgt_parts = target.split(".")
            cursor = data
            for part in tgt_parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[tgt_parts[-1]] = value

    for k, v in list(data.items()):
        if isinstance(v, dict):
            _apply_aliases(v)
    return data


_LIST_SPLIT_RE = re.compile(r"[,\n;•]+")
TRUE_VALUES = {"true", "yes", "1", "ja"}
FALSE_VALUES = {"false", "no", "0", "nein"}


def _filter_unknown_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Remove keys not present in the schema to avoid validation errors."""

    def _walk(d: dict[str, Any], prefix: str = "") -> None:
        for key in list(d.keys()):
            path = f"{prefix}{key}" if prefix else key
            value = d[key]
            if isinstance(value, dict):
                if any(f.startswith(path + ".") for f in ALL_FIELDS):
                    _walk(value, path + ".")
                    if not value and path not in ALL_FIELDS:
                        del d[key]
                elif path not in ALL_FIELDS:
                    del d[key]
            else:
                if path not in ALL_FIELDS:
                    del d[key]

    _walk(data)
    return data


def _coerce_types(data: dict[str, Any]) -> dict[str, Any]:
    """Convert obvious mismatched types based on the schema."""

    def _walk(d: dict[str, Any], prefix: str = "") -> None:
        for key, value in list(d.items()):
            path = f"{prefix}{key}" if prefix else key
            if isinstance(value, dict):
                _walk(value, path + ".")
                continue

            if path in LIST_FIELDS and isinstance(value, str):
                cleaned = re.sub(r"^[^:]*:\s*", "", value)
                parts = [p.strip() for p in _LIST_SPLIT_RE.split(cleaned) if p.strip()]
                d[key] = parts
            elif path in BOOL_FIELDS and isinstance(value, str):
                lower = value.strip().lower()
                if lower in TRUE_VALUES:
                    d[key] = True
                elif lower in FALSE_VALUES:
                    d[key] = False
            elif path in INT_FIELDS and isinstance(value, str):
                match = re.search(r"-?\d+", value)
                if match:
                    d[key] = int(match.group())
            elif path in FLOAT_FIELDS and isinstance(value, str):
                match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", "."))
                if match:
                    d[key] = float(match.group())

    _walk(data)
    return data


def parse_extraction(raw: str) -> NeedAnalysisProfile:
    """
    Parse LLM output into a validated NeedAnalysisProfile.

    Strategy:
      1) Try strict json.loads(raw).
      2) Strip code fences/BOM, try json.loads again.
      3) Extract first balanced {...} block and json.loads it.
      4) If all fail, re-raise the last JSONDecodeError.

    Always returns an object validated against :class:`NeedAnalysisProfile`
    to ensure all expected keys exist (with ``""``/``[]`` defaults).
    """
    last_err = None

    def _process(payload: str) -> NeedAnalysisProfile:
        data = _coerce_types(_filter_unknown_fields(_apply_aliases(json.loads(payload))))
        return NeedAnalysisProfile.model_validate(data)

    # 1) direct parse
    try:
        return _process(raw)
    except Exception as e:
        last_err = e

    # 2) sanitize and retry
    try:
        sanitized = _strip_code_fences(raw).strip()
        return _process(sanitized)
    except Exception as e:
        last_err = e

    # 3) balanced extraction
    block = _first_balanced_json(sanitized if "sanitized" in locals() else raw)
    if block:
        try:
            return _process(block)
        except Exception as e:
            last_err = e

    # 4) give up
    if last_err:
        raise last_err
    raise ValueError("Empty response; no JSON to parse.")
