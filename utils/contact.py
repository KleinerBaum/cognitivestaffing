"""Helpers for working with contact information."""

from __future__ import annotations

import re
from typing import Iterable

_GENERIC_TOKENS = {
    "info",
    "kontakt",
    "contact",
    "karriere",
    "career",
    "bewerbung",
    "bewerbungen",
    "jobs",
    "job",
    "hello",
    "hallo",
    "support",
    "mail",
    "office",
    "team",
    "service",
    "bewerber",
    "recruiting",
    "talent",
    "talents",
    "hr",
}

_TOKEN_SPLIT_RE = re.compile(r"[._\-\s]+")
_NON_LETTER_RE = re.compile(r"[^A-Za-zÄÖÜäöüß]+", re.UNICODE)


def _title_case_token(token: str) -> str:
    """Return ``token`` in title case while keeping initials uppercase."""

    if len(token) == 1:
        return token.upper()
    return token[:1].upper() + token[1:]


def _clean_token(token: str) -> str:
    """Return a cleaned token with digits and symbols removed."""

    cleaned = _NON_LETTER_RE.sub("", token)
    return cleaned


def _iter_candidate_tokens(local_part: str) -> Iterable[str]:
    """Yield candidate tokens from ``local_part`` of an email address."""

    for raw in _TOKEN_SPLIT_RE.split(local_part):
        raw = raw.strip()
        if not raw:
            continue
        cleaned = _clean_token(raw)
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered in _GENERIC_TOKENS:
            continue
        yield _title_case_token(cleaned)


def infer_contact_name_from_email(email: str | None) -> str:
    """Infer a likely contact name from ``email``.

    Args:
        email: Email address to analyse.

    Returns:
        Suggested name with title-cased tokens, or an empty string when no
        suitable hint can be derived.
    """

    if not email or "@" not in email:
        return ""

    local_part = email.split("@", 1)[0].strip("._- ")
    if not local_part:
        return ""

    tokens = list(_iter_candidate_tokens(local_part))
    if not tokens:
        return ""

    if len(tokens) == 1 and len(tokens[0]) <= 2:
        # Avoid suggesting generic 1-2 letter codes such as "HR".
        return ""

    return " ".join(tokens)


__all__ = ["infer_contact_name_from_email"]
