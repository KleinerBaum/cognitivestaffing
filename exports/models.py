"""Export utilities for the RecruitingWizard schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.schema import RecruitingWizard, WIZARD_KEYS_CANONICAL, is_wizard_schema_enabled


class WizardExportError(RuntimeError):
    """Raised when the RecruitingWizard export cannot be produced."""


@dataclass(slots=True)
class RecruitingWizardExport:
    """Wrapper providing conversion helpers for the canonical wizard schema."""

    payload: RecruitingWizard

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any] | RecruitingWizard, *, require_flag: bool = True
    ) -> "RecruitingWizardExport":
        """Validate ``payload`` against the wizard schema and return an export wrapper."""

        if require_flag and not is_wizard_schema_enabled():
            raise WizardExportError("RecruitingWizard schema is disabled (set SCHEMA_WIZARD_V1=1 to enable exports).")
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


__all__ = ["RecruitingWizardExport", "WizardExportError"]
