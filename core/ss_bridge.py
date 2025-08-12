"""Helpers for mapping between session state and schema objects."""

from __future__ import annotations

from .schema import ALL_FIELDS, ALIASES, LIST_FIELDS, VacalyserJD, coerce_and_fill


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

    # remove deprecated alias keys to avoid duplicate form fields
    for alias in ALIASES:
        ss.pop(alias, None)


def from_session_state(ss: dict) -> VacalyserJD:
    """Build a :class:`VacalyserJD` from session state values.

    Text area fields are split on newlines to re-create lists. Alias keys are
    preserved so that older state snapshots remain compatible.

    Args:
        ss: Session state dictionary.

    Returns:
        A normalised :class:`VacalyserJD` instance.
    """

    data: dict[str, object] = {}
    for key, value in ss.items():
        target = ALIASES.get(key, key)
        if target in LIST_FIELDS and isinstance(value, str):
            value = [line for line in value.splitlines() if line.strip()]
        data[target] = value
    return coerce_and_fill(data)
