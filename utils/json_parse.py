"""
Robust JSON parsing utilities for LLM extraction output.

Implements:
- CS-PAR-01: Strict parser with sanitization
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, Optional

from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill


_CODE_FENCE_RE = re.compile(
    r"^```[a-zA-Z0-9_+-]*\s*$|^```\s*$|^\uFEFF|^\ufeff",  # fences or BOM at line start
    flags=re.MULTILINE,
)
_TRAILING_COMMAS_RE = re.compile(r",\s*([}\]])")


def _decode_largest_object(raw: str) -> Mapping[str, Any] | None:
    """Return the largest JSON object decoded from any brace offset in ``raw``."""

    decoder = json.JSONDecoder()
    best: tuple[int, Mapping[str, Any]] | None = None

    for match in re.finditer(r"{", raw):
        try:
            obj, end = decoder.raw_decode(raw, match.start())
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, Mapping):
            continue
        length = end - match.start()
        if best is None or length > best[0]:
            best = (length, dict(obj))

    if best is None:
        return None
    return best[1]


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


def _trim_to_object(candidate: str) -> str:
    """Return ``candidate`` cropped to the outermost JSON object if present."""

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return candidate[start : end + 1]
    return candidate


def _strip_trailing_commas(candidate: str) -> str:
    """Remove trailing commas before closing braces/brackets."""

    return _TRAILING_COMMAS_RE.sub(r"\1", candidate)


def _balance_braces(candidate: str) -> str:
    """Append missing closing braces when the payload is clearly unbalanced."""

    opens = candidate.count("{")
    closes = candidate.count("}")
    if opens > closes:
        candidate = f"{candidate}{'}' * (opens - closes)}"
    return candidate


def _largest_balanced_json(s: str) -> Optional[str]:
    """Return the largest balanced JSON object found within ``s``."""

    if not s:
        return None

    in_str = False
    esc = False
    depth = 0
    start = -1
    blocks: list[str] = []

    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                blocks.append(s[start : i + 1])  # noqa: E203
    if not blocks:
        return None
    return max(blocks, key=len)


def _iter_candidates(raw: str) -> Iterable[str]:
    """Yield sanitised candidates for JSON parsing attempts."""

    sanitized = _strip_code_fences(raw).strip()
    trimmed = _trim_to_object(sanitized)
    stripped = _strip_trailing_commas(trimmed)
    balanced = _balance_braces(stripped)

    seen: set[str] = set()

    for candidate in (sanitized, trimmed, stripped, balanced):
        key = candidate.strip()
        if key and key not in seen:
            seen.add(key)
            yield key

    largest_block = _largest_balanced_json(sanitized)
    if largest_block:
        for candidate in (
            largest_block,
            _strip_trailing_commas(largest_block),
            _balance_braces(_strip_trailing_commas(largest_block)),
        ):
            key = candidate.strip()
            if key and key not in seen:
                seen.add(key)
                yield key


def _safe_json_loads(raw: str) -> Mapping[str, Any]:
    """Parse ``raw`` into a mapping using lightweight repair strategies."""

    last_err: Exception | None = None
    candidates = list(_iter_candidates(raw))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception as exc:  # JSONDecodeError or similar
            if isinstance(exc, json.JSONDecodeError) and "Unterminated string" in exc.msg:
                tail_stripped = candidate.rstrip()
                if tail_stripped.endswith("}"):
                    closed_string = _balance_braces(f'{tail_stripped[:-1]}"}}')
                    try:
                        parsed = json.loads(closed_string)
                    except Exception:  # pragma: no cover - defensive
                        parsed = None
                    if isinstance(parsed, Mapping):
                        return dict(parsed)
                repaired_candidate = _balance_braces(f'{candidate}"')
                try:
                    parsed = json.loads(repaired_candidate)
                except Exception:  # pragma: no cover - defensive
                    truncated = _balance_braces(f'{candidate[: exc.pos]}"')
                    try:
                        parsed = json.loads(truncated)
                    except Exception:  # pragma: no cover - defensive
                        last_err = exc
                        continue
                if isinstance(parsed, Mapping):
                    return dict(parsed)
            last_err = exc
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
        last_err = ValueError("Parsed JSON is not an object")
    for candidate in candidates:
        decoded = _decode_largest_object(candidate)
        if decoded is not None:
            return decoded
    decoded = _decode_largest_object(raw)
    if decoded is not None:
        return decoded
    if last_err:
        raise last_err
    raise ValueError("Empty response; no JSON to parse.")


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


TRUE_VALUES = {"true", "yes", "1", "ja"}
FALSE_VALUES = {"false", "no", "0", "nein"}


def parse_extraction(raw: str) -> NeedAnalysisProfile:
    """
    Parse LLM output into a validated NeedAnalysisProfile.

    Strategy:
      1) Try strict json.loads(raw).
      2) Strip code fences/BOM and trim to the most plausible JSON object.
      3) Apply lightweight repair (trailing commas, unbalanced braces).
      4) Extract the largest balanced {...} block and retry.
      5) If all fail, re-raise the last JSONDecodeError.

    Always returns an object validated against :class:`NeedAnalysisProfile`
    to ensure all expected keys exist (with ``""``/``[]`` defaults).
    """
    last_err: Exception | None = None

    try:
        parsed = _safe_json_loads(raw)
        return coerce_and_fill(parsed)
    except Exception as exc:
        last_err = exc

    block = _first_balanced_json(raw)
    if block:
        try:
            parsed = _safe_json_loads(block)
            return coerce_and_fill(parsed)
        except Exception as exc:  # pragma: no cover - defensive
            last_err = exc

    if last_err:
        raise last_err
    raise ValueError("Empty response; no JSON to parse.")
