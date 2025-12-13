"""Helpers for parsing and repairing JSON payloads returned by LLMs."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

logger = logging.getLogger(__name__)

RepairFunction = Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]] | None], Mapping[str, Any] | None]


class JsonRepairStatus(Enum):
    """Enumeration describing the outcome of a JSON repair attempt."""

    OK = "ok"
    REPAIRED = "repaired"
    FAILED = "failed"


@dataclass(frozen=True)
class JsonRepairResult:
    """Result returned by :func:`parse_json_with_repair`."""

    payload: Mapping[str, Any] | None
    status: JsonRepairStatus
    issues: list[str]

    @property
    def low_confidence(self) -> bool:
        """Return ``True`` when the payload required repair."""

        return self.status is JsonRepairStatus.REPAIRED


def _trim_noise(raw: str) -> str:
    """Return ``raw`` limited to the outermost JSON object if present."""

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _strip_trailing_commas(candidate: str) -> str:
    """Remove trailing commas before closing braces/brackets."""

    return re.sub(r",\s*([}\]])", r"\1", candidate)


def _balance_braces(candidate: str) -> str:
    """Append missing closing braces when clearly unbalanced."""

    opens = candidate.count("{")
    closes = candidate.count("}")
    if opens > closes:
        candidate = f"{candidate}{'}' * (opens - closes)}"
    return candidate


def _attempt_local_repair(raw: str) -> Mapping[str, Any] | None:
    """Try lightweight, local fixes for malformed JSON strings."""

    from utils import json_parse

    parsed: Mapping[str, Any] | None
    try:
        parsed = json_parse._safe_json_loads(raw)
    except Exception:
        parsed = json_parse._decode_largest_object(raw)
    if isinstance(parsed, Mapping):
        return dict(parsed)

    attempts: list[str] = []
    trimmed = _trim_noise(raw)
    attempts.append(trimmed)
    attempts.append(_strip_trailing_commas(trimmed))
    attempts.append(_balance_braces(_strip_trailing_commas(trimmed)))

    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return None


def parse_json_with_repair(
    raw: str,
    *,
    errors: Sequence[Mapping[str, Any]] | None = None,
    repair_func: RepairFunction | None = None,
) -> JsonRepairResult:
    """Parse ``raw`` into a JSON object and attempt repair if needed.

    The function separates three outcomes:
    - :class:`JsonRepairStatus.OK` when the payload parses without modification.
    - :class:`JsonRepairStatus.REPAIRED` when the payload is recovered via
      heuristic cleanup or a provided ``repair_func``.
    - :class:`JsonRepairStatus.FAILED` when parsing and repair both fail.
    """

    issues: list[str] = []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        message = f"JSON parsing error at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        issues.append(message)
        repaired: Mapping[str, Any] | None = _attempt_local_repair(raw)
        if repaired is not None:
            return JsonRepairResult(payload=repaired, status=JsonRepairStatus.REPAIRED, issues=issues)
        if repair_func is not None:
            repaired = repair_func({}, errors or [{"loc": ("<root>",), "msg": message}])
            if isinstance(repaired, Mapping):
                return JsonRepairResult(payload=dict(repaired), status=JsonRepairStatus.REPAIRED, issues=issues)
        logger.debug("JSON repair failed for payload: %s", message)
        return JsonRepairResult(payload=None, status=JsonRepairStatus.FAILED, issues=issues)

    if not isinstance(parsed, Mapping):
        error_message = "Model returned JSON that is not an object."
        issues.append(error_message)
        if repair_func is not None:
            repaired = repair_func({}, errors or [{"loc": ("<root>",), "msg": error_message}])
            if isinstance(repaired, Mapping):
                return JsonRepairResult(payload=dict(repaired), status=JsonRepairStatus.REPAIRED, issues=issues)
        return JsonRepairResult(payload=None, status=JsonRepairStatus.FAILED, issues=issues)

    return JsonRepairResult(payload=dict(parsed), status=JsonRepairStatus.OK, issues=issues)


__all__ = ["JsonRepairResult", "JsonRepairStatus", "parse_json_with_repair"]
