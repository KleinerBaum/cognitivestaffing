from __future__ import annotations

from typing import Final, Tuple
from pydantic import EmailStr, ValidationError
from pydantic.type_adapter import TypeAdapter

from constants.keys import ProfilePaths
from wizard._logic import _update_profile

LocalizedText = Tuple[str, str]

_EMAIL_ADAPTER: Final[TypeAdapter[EmailStr]] = TypeAdapter(EmailStr)

_CONTACT_EMAIL_REQUIRED_ERROR: Final[LocalizedText] = (
    "Bitte Kontakt-E-Mail eintragen.",
    "Please enter the contact email.",
)
_CONTACT_EMAIL_INVALID_ERROR: Final[LocalizedText] = (
    "Bitte gültige E-Mail-Adresse verwenden.",
    "Please enter a valid email address.",
)
_PRIMARY_CITY_REQUIRED_ERROR: Final[LocalizedText] = (
    "Bitte primären Standort eintragen.",
    "Please enter the primary city.",
)


def persist_contact_email(raw_value: str | None) -> tuple[str | None, LocalizedText | None]:
    """Validate and persist the company contact email."""

    candidate = (raw_value or "").strip()
    if not candidate:
        _update_profile(
            ProfilePaths.COMPANY_CONTACT_EMAIL,
            None,
            session_value=raw_value or "",
        )
        return None, _CONTACT_EMAIL_REQUIRED_ERROR
    try:
        normalized = _EMAIL_ADAPTER.validate_python(candidate)
    except (ValidationError, TypeError):
        _update_profile(
            ProfilePaths.COMPANY_CONTACT_EMAIL,
            None,
            session_value=raw_value or "",
        )
        return None, _CONTACT_EMAIL_INVALID_ERROR
    _update_profile(
        ProfilePaths.COMPANY_CONTACT_EMAIL,
        normalized,
        session_value=normalized,
    )
    return normalized, None


def persist_primary_city(raw_value: str | None) -> tuple[str | None, LocalizedText | None]:
    """Validate and persist the primary city."""

    candidate = (raw_value or "").strip()
    if not candidate:
        _update_profile(
            ProfilePaths.LOCATION_PRIMARY_CITY,
            None,
            session_value=raw_value or "",
        )
        return None, _PRIMARY_CITY_REQUIRED_ERROR
    _update_profile(
        ProfilePaths.LOCATION_PRIMARY_CITY,
        candidate,
        session_value=candidate,
    )
    return candidate, None


__all__ = ["persist_contact_email", "persist_primary_city"]
