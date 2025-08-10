"""Helpers for mapping between session state and schema objects."""

from __future__ import annotations

from .schema import ALL_FIELDS, LIST_FIELDS, VacalyserJD, coerce_and_fill


def to_session_state(jd: VacalyserJD, ss: dict) -> None:
    """Populate session state with values from a job description.

    List fields are joined by newlines so they can be displayed in Streamlit
    text areas.

    Args:
        jd: The job description to serialise.
        ss: Session state dictionary to update in-place.
    """

    for field in ALL_FIELDS:
        value = getattr(jd, field)
        if field in LIST_FIELDS:
            ss[field] = "\n".join(value)
        else:
            ss[field] = value


def from_session_state(ss: dict) -> VacalyserJD:
    """Build a :class:`VacalyserJD` from session state values.

    Text area fields are split on newlines to re-create lists.

    Args:
        ss: Session state dictionary.

    Returns:
        A normalised :class:`VacalyserJD` instance.
    """

    data: dict[str, object] = {}
    for field in ALL_FIELDS:
        value = ss.get(field, [] if field in LIST_FIELDS else "")
        if field in LIST_FIELDS and isinstance(value, str):
            value = [line for line in value.splitlines() if line.strip()]
        data[field] = value
    return coerce_and_fill(data)
