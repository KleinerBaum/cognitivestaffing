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
from core.schema import ALIASES


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


def _apply_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Map alias keys in ``data`` to schema paths."""
    for alias, target in ALIASES.items():
        src_parts = alias.split(".")
        cursor = data
        parent = None
        for part in src_parts:
            if not isinstance(cursor, dict) or part not in cursor:
                break
            parent = cursor
            cursor = cursor[part]
        else:
            value = cursor
            if parent is not None:
                del parent[src_parts[-1]]
            tgt_parts = target.split(".")
            cursor = data
            for part in tgt_parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[tgt_parts[-1]] = value
    for k, v in list(data.items()):
        if isinstance(v, dict):
            _apply_aliases(v)
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

    # 1) direct parse
    try:
        return NeedAnalysisProfile.model_validate(_apply_aliases(json.loads(raw)))
    except Exception as e:
        last_err = e

    # 2) sanitize and retry
    try:
        sanitized = _strip_code_fences(raw).strip()
        return NeedAnalysisProfile.model_validate(_apply_aliases(json.loads(sanitized)))
    except Exception as e:
        last_err = e

    # 3) balanced extraction
    block = _first_balanced_json(sanitized if "sanitized" in locals() else raw)
    if block:
        try:
            return NeedAnalysisProfile.model_validate(_apply_aliases(json.loads(block)))
        except Exception as e:
            last_err = e

    # 4) give up
    if last_err:
        raise last_err
    raise ValueError("Empty response; no JSON to parse.")
