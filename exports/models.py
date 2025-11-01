"""Export utilities for the RecruitingWizard schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.schema import RecruitingWizard, WIZARD_KEYS_CANONICAL


@dataclass(slots=True)
class RecruitingWizardExport:
    """Wrapper providing conversion helpers for the canonical wizard schema."""

    payload: RecruitingWizard

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any] | RecruitingWizard
    ) -> "RecruitingWizardExport":
        """Validate ``payload`` against the wizard schema and return an export wrapper."""

        if isinstance(payload, RecruitingWizard):
            model = payload
        else:
            model = RecruitingWizard.model_validate(payload)
        return cls(payload=model)

    def to_dict(self) -> dict[str, Any]:
        """Return the payload as a JSON-serialisable dictionary."""

        return self.payload.model_dump(mode="json")

    def canonical_keys(self) -> tuple[str, ...]:
        """Expose the canonical dot-paths for downstream processors."""

        return WIZARD_KEYS_CANONICAL


__all__ = ["RecruitingWizardExport"]
