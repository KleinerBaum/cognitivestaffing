from .schema import ALL_FIELDS, ALIASES, LIST_FIELDS, VacalyserJD, coerce_and_fill

def to_session_state(jd: VacalyserJD, ss: dict) -> None:
    """Populate session state dict with values from a VacalyserJD object."""
    for field in ALL_FIELDS:
        if "." in field:
            group, sub = field.split(".", 1)
            value = getattr(getattr(jd, group), sub)
        else:
            value = getattr(jd, field)
        if field in LIST_FIELDS:
            # join list elements with newlines for textarea display
            ss[field] = "\n".join(value)
        else:
            ss[field] = value
    # Remove deprecated alias keys to avoid duplicates in form
    for alias in ALIASES:
        ss.pop(alias, None)

def from_session_state(ss: dict) -> VacalyserJD:
    """Build a VacalyserJD model from the session state values."""
    data: dict[str, Any] = {}
    for key, value in ss.items():
        target = ALIASES.get(key, key)
        # If the target expects a list but value is a multi-line string, split it
        if target in LIST_FIELDS and isinstance(value, str):
            # split on newline, ignoring empty lines
            value = [line for line in value.splitlines() if line.strip()]
        # Assign into data (handling nested keys)
        if "." in target:
            group, sub = target.split(".", 1)
            data.setdefault(group, {})[sub] = value
        else:
            data[target] = value
    return coerce_and_fill(data)
