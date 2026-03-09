"""Central registry for wizard required-field validators.

This module is the single extension point for field-level validators that must
run consistently across wizard navigation, metadata-based critical-field
checks, and tests.

To add a new validator:
1. implement a ``persist_*`` validator returning ``(normalized_value, error)``;
2. register the profile path in ``REQUIRED_FIELD_VALIDATORS`` below.

All callers should import the mapping from this module instead of defining
local dictionaries.
"""

from __future__ import annotations

from typing import Callable, Final, TypeAlias

from constants.keys import ProfilePaths
from wizard.company_validators import persist_contact_email, persist_primary_city

LocalizedText: TypeAlias = tuple[str, str]
Validator: TypeAlias = Callable[[str | None], tuple[str | None, LocalizedText | None]]

REQUIRED_FIELD_VALIDATORS: Final[dict[str, Validator]] = {
    str(ProfilePaths.COMPANY_CONTACT_EMAIL): persist_contact_email,
    str(ProfilePaths.LOCATION_PRIMARY_CITY): persist_primary_city,
}

PROFILE_VALIDATED_FIELDS: Final[set[str]] = set(REQUIRED_FIELD_VALIDATORS)

__all__ = ["LocalizedText", "PROFILE_VALIDATED_FIELDS", "REQUIRED_FIELD_VALIDATORS", "Validator"]
