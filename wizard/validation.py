from __future__ import annotations

import copy
from typing import Callable, Collection, Mapping, Sequence

from constants.keys import StateKeys
from wizard._logic import get_in
from wizard.followups import followup_has_response
from wizard.metadata import PAGE_FOLLOWUP_PREFIXES
from wizard.services.validation import is_value_present
from wizard.types import LocalizedText
from wizard_pages.base import WizardPage


def validate_required_field_inputs(
    fields: Sequence[str],
    *,
    required_field_validators: Mapping[str, Callable[[str | None], tuple[str | None, LocalizedText | None]]],
    value_resolver: Callable[[Mapping[str, object], str, object | None], object | None],
    session_state: Mapping[str, object],
) -> dict[str, LocalizedText]:
    """Re-run profile-bound validators for ``fields`` using widget/profile state."""

    profile_raw = session_state.get(StateKeys.PROFILE, {}) or {}
    profile: Mapping[str, object] = profile_raw if isinstance(profile_raw, Mapping) else {}
    errors: dict[str, LocalizedText] = {}
    for field in fields:
        validator = required_field_validators.get(field)
        if validator is None:
            continue
        raw_value_obj = session_state.get(field)
        if isinstance(raw_value_obj, str):
            raw_value: str | None = raw_value_obj
        else:
            profile_value = value_resolver(profile, field, None)
            raw_value = profile_value if isinstance(profile_value, str) else None
        _, error = validator(raw_value)
        if error:
            errors[field] = error
    return errors


def missing_inline_followups(
    page: WizardPage,
    *,
    profile: Mapping[str, object],
    followups: object,
    session_state: Mapping[str, object],
) -> list[str]:
    """Identify critical follow-ups that still lack a response."""

    prefixes = PAGE_FOLLOWUP_PREFIXES.get(page.key, ())
    if not prefixes:
        return []
    if not isinstance(followups, list):
        return []
    missing: list[str] = []
    for question in followups:
        if not isinstance(question, Mapping):
            continue
        field = question.get("field")
        if not isinstance(field, str) or not field:
            continue
        if not any(field.startswith(prefix) for prefix in prefixes):
            continue
        if question.get("priority") != "critical":
            continue
        value = session_state.get(field)
        if not followup_has_response(value):
            value = get_in(profile, field, None)
        if not followup_has_response(value):
            missing.append(field)
    return missing


def resolve_missing_required_fields(
    page: WizardPage,
    *,
    required_field_validators: Mapping[str, Callable[[str | None], tuple[str | None, LocalizedText | None]]],
    validated_fields: Collection[str],
    value_resolver: Callable[[Mapping[str, object], str, object | None], object | None],
    session_state: Mapping[str, object],
    validator: Callable[[Sequence[str]], dict[str, LocalizedText]] | None = None,
) -> tuple[list[str], dict[str, LocalizedText]]:
    """Determine missing data for a page and capture validation errors."""

    profile_raw = session_state.get(StateKeys.PROFILE, {}) or {}
    profile: Mapping[str, object] = profile_raw if isinstance(profile_raw, Mapping) else {}
    profile_snapshot = copy.deepcopy(profile)
    missing: list[str] = []
    validation_errors: dict[str, LocalizedText] = {}
    required_fields = tuple(page.required_fields or ())
    if required_fields:
        validation_errors = (
            validator(required_fields)
            if validator is not None
            else validate_required_field_inputs(
                required_fields,
                required_field_validators=required_field_validators,
                value_resolver=value_resolver,
                session_state=session_state,
            )
        )
        for field in required_fields:
            if field in validated_fields:
                value = None
            else:
                value = session_state.get(field)
            if not is_value_present(value):
                value = value_resolver(profile_snapshot, field, None)
            if not is_value_present(value):
                missing.append(field)
        if validation_errors:
            for field in validation_errors:
                if field not in missing:
                    missing.append(field)
    inline_missing = missing_inline_followups(
        page,
        profile=profile_snapshot,
        followups=session_state.get(StateKeys.FOLLOWUPS),
        session_state=session_state,
    )
    if inline_missing:
        missing.extend(inline_missing)
    if not missing:
        return [], validation_errors
    return list(dict.fromkeys(missing)), validation_errors
