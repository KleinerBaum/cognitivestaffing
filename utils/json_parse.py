"""
Robust JSON parsing utilities for LLM extraction output.

Implements:
- CS-PAR-01: Strict parser with sanitization
"""
from __future__ import annotations

import json
import re
from typing import Optional

from core.schema import VacalyserJD, coerce_and_fill


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
    s = s.lstrip("\ufeff").lstrip("\uFEFF")
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
                    return s[start : i + 1]
    return None


def parse_extraction(raw: str) -> VacalyserJD:
    """
    Parse LLM output into a validated VacalyserJD.

    Strategy:
      1) Try strict json.loads(raw).
      2) Strip code fences/BOM, try json.loads again.
      3) Extract first balanced {...} block and json.loads it.
      4) If all fail, re-raise the last JSONDecodeError.

    Always returns an object filtered through coerce_and_fill to ensure
    all expected keys exist (with ''/[] defaults).
    """
    last_err = None

    # 1) direct parse
    try:
        return coerce_and_fill(json.loads(raw))
    except Exception as e:
        last_err = e

    # 2) sanitize and retry
    try:
        sanitized = _strip_code_fences(raw).strip()
        return coerce_and_fill(json.loads(sanitized))
    except Exception as e:
        last_err = e

    # 3) balanced extraction
    block = _first_balanced_json(sanitized if "sanitized" in locals() else raw)
    if block:
        try:
            return coerce_and_fill(json.loads(block))
        except Exception as e:
            last_err = e

    # 4) give up
    if last_err:
        raise last_err
    raise ValueError("Empty response; no JSON to parse.")
