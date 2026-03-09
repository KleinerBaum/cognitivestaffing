"""Cue detection helpers for targeted requirement/responsibility extraction."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

TARGETED_FIELDS: tuple[str, ...] = (
    "requirements.hard_skills_required",
    "requirements.soft_skills_required",
    "responsibilities.items",
)

_FIELD_CUES: dict[str, tuple[str, ...]] = {
    "requirements.hard_skills_required": (
        "must have",
        "required",
        "requirements",
        "qualifications",
        "anforderungen",
        "qualifikation",
        "erfahrung in",
        "kenntnisse",
    ),
    "requirements.soft_skills_required": (
        "soft skills",
        "communication",
        "team",
        "stakeholder",
        "selbstständig",
        "kommunikation",
        "teamfähigkeit",
        "zusammenarbeit",
    ),
    "responsibilities.items": (
        "you will",
        "your role",
        "responsibilities",
        "what you'll do",
        "aufgaben",
        "verantwortlichkeiten",
        "du wirst",
        "ihr profil",
        "tätigkeiten",
    ),
}


def detect_targeted_cues(text: str, fields: Iterable[str]) -> dict[str, list[str]]:
    """Return cue snippets per field using DE/EN keyword matching."""

    if not text.strip():
        return {}

    candidates = [line.strip(" -•\t") for line in re.split(r"[\n\r\.\!\?;]+", text) if line.strip()]
    lowered = [segment.casefold() for segment in candidates]
    matched: dict[str, list[str]] = defaultdict(list)

    for field in fields:
        cues = _FIELD_CUES.get(field, ())
        for index, segment in enumerate(lowered):
            if any(cue in segment for cue in cues):
                snippet = candidates[index].strip()
                if snippet and snippet not in matched[field]:
                    matched[field].append(snippet)

    return dict(matched)
