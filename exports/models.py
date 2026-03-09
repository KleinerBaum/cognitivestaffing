"""Export utilities for the RecruitingWizard schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.schema import (
    RecruitingWizard,
    WIZARD_KEYS_CANONICAL,
    canonicalize_wizard_payload,
)


def _get_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_value(payload: dict[str, Any], path: str, value: Any) -> None:
    current: dict[str, Any] = payload
    parts = path.split(".")
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def apply_field_metadata_to_payload(
    payload: Mapping[str, Any],
    *,
    mark_unconfirmed: bool,
    exclude_unconfirmed: bool,
) -> dict[str, Any]:
    """Mark or exclude unconfirmed heuristic estimates in export payloads."""

    cloned = dict(payload)
    meta = cloned.get("meta") if isinstance(cloned.get("meta"), Mapping) else {}
    field_metadata = meta.get("field_metadata") if isinstance(meta, Mapping) else {}
    if not isinstance(field_metadata, Mapping):
        return cloned

    if not mark_unconfirmed and not exclude_unconfirmed:
        return cloned

    for path, entry in field_metadata.items():
        if not isinstance(path, str) or not isinstance(entry, Mapping):
            continue
        source = str(entry.get("source") or "").lower()
        confirmed = bool(entry.get("confirmed", False))
        if source != "heuristic" or confirmed:
            continue

        value = _get_value(cloned, path)
        if value in (None, "", [], {}):
            continue

        if exclude_unconfirmed:
            _set_value(cloned, path, None)
            continue

        if mark_unconfirmed:
            if isinstance(value, str):
                _set_value(cloned, path, f"{value} [UNCONFIRMED_ESTIMATE]")
            elif isinstance(value, list):
                _set_value(cloned, path, [f"{item} [UNCONFIRMED_ESTIMATE]" for item in value])

    return cloned


@dataclass(slots=True)
class RecruitingWizardExport:
    """Wrapper providing conversion helpers for the canonical wizard schema."""

    payload: RecruitingWizard

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | RecruitingWizard) -> "RecruitingWizardExport":
        """Validate ``payload`` against the wizard schema and return an export wrapper."""

        if isinstance(payload, RecruitingWizard):
            model = payload
        else:
            canonical = canonicalize_wizard_payload(payload)
            model = RecruitingWizard.model_validate(canonical)
        return cls(payload=model)

    def to_dict(self) -> dict[str, Any]:
        """Return the payload as a JSON-serialisable dictionary."""

        return self.payload.model_dump(mode="json")

    def canonical_keys(self) -> tuple[str, ...]:
        """Expose the canonical dot-paths for downstream processors."""

        return WIZARD_KEYS_CANONICAL


__all__ = ["RecruitingWizardExport", "apply_field_metadata_to_payload"]
