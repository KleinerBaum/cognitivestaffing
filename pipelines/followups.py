"""Follow-up question generation pipeline."""

from __future__ import annotations

from typing import Any

from wizard.services.followups import generate_followups as _generate_followups

__all__ = ["generate_followups"]


def generate_followups(
    vacancy_json: dict,
    lang: str,
    vector_store_id: str | None = None,
) -> dict[str, Any]:
    """Generate prioritised follow-up questions for a vacancy profile."""

    return _generate_followups(
        vacancy_json,
        mode="fast",
        locale=lang,
        vector_store_id=vector_store_id,
    )
