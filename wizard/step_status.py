"""Helpers for computing wizard step completion status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from wizard.metadata import field_belongs_to_page
from wizard.missing_fields import get_path_value, missing_fields
from wizard.services.gaps import load_critical_fields
from wizard_pages.base import WizardPage


__all__ = ["StepMissing", "compute_step_missing", "is_step_complete", "iter_step_missing_fields"]


def _critical_fields_for_step(step_meta: WizardPage) -> tuple[str, ...]:
    return tuple(field for field in load_critical_fields() if field_belongs_to_page(field, step_meta.key))


@dataclass(frozen=True)
class StepMissing:
    """Missing required and critical field lists for a wizard step."""

    required: list[str]
    critical: list[str]


def compute_step_missing(profile: object, step_meta: WizardPage) -> StepMissing:
    """Compute missing required and critical fields for ``step_meta``."""  # GREP:STEP_STATUS_V1

    profile_data = get_path_value(profile, "")
    required_fields = tuple(step_meta.required_fields or ())
    missing_required = missing_fields(profile_data, required_fields) if required_fields else []
    critical_fields = _critical_fields_for_step(step_meta)
    missing_critical = missing_fields(profile_data, critical_fields) if critical_fields else []
    return StepMissing(required=missing_required, critical=missing_critical)


def is_step_complete(profile: object, step_meta: WizardPage) -> bool:
    """Return ``True`` when ``step_meta`` has no missing required/critical fields."""

    missing = compute_step_missing(profile, step_meta)
    return not missing.required and not missing.critical


def iter_step_missing_fields(missing: StepMissing) -> Iterable[str]:
    """Return an ordered iterable of all missing fields."""

    return tuple(dict.fromkeys([*missing.required, *missing.critical]))
