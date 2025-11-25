"""Heuristics to separate responsibilities from requirements bullets."""

from __future__ import annotations

import re
from typing import Literal, Sequence

_BULLET_PREFIX_RE = re.compile(r"^[\s\-–—•*·\d.)]+")

_RESPONSIBILITY_PREFIXES: tuple[str, ...] = (
    "you will",
    "you'll",
    "you are responsible",
    "in this role",
    "lead",
    "manage",
    "drive",
    "own",
    "oversee",
    "coordinate",
    "build",
    "develop",
    "design",
    "implement",
    "deliver",
    "execute",
    "ensure",
    "advise",
    "consult",
    "partner",
    "coach",
    "mentor",
    "analyze",
    "analyse",
    "berätst",
    "leitest",
    "entwickelst",
    "steuerst",
    "konzipierst",
    "gestaltest",
    "übernimmst",
    "uebernimmst",
    "analysierst",
    "planst",
    "führst",
    "fuehrst",
    "betreust",
    "koordinierst",
    "unterstützt",
    "unterstuetzt",
)

_REQUIREMENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d+\s*\+?\s*(?:years|yrs|jahr|jahre)\b.*\berfahrung\b", re.IGNORECASE),
    re.compile(r"\bexperience\s+(?:with|in|of)\b", re.IGNORECASE),
    re.compile(r"\berfahrung\b", re.IGNORECASE),
    re.compile(r"bringst du mit", re.IGNORECASE),
    re.compile(r"\bkenntnisse\b", re.IGNORECASE),
    re.compile(r"\bknowledge\b", re.IGNORECASE),
    re.compile(r"\bdegree\b|\bbachelor'?s?\b|\bmaster'?s?\b|\bstudium\b|\babschluss\b", re.IGNORECASE),
    re.compile(r"\bcertification\b|\bcertified\b|\bzertifikat\b|\bzertifizierung\b", re.IGNORECASE),
    re.compile(r"\bfluent\b|\bproficienc", re.IGNORECASE),
    re.compile(r"\bability to\b|\bability\b|\bfähigkeit\b|\bfähigkeiten\b|\bfaehigkeit\b", re.IGNORECASE),
    re.compile(r"\bskill\b|\bfertigkeit\b", re.IGNORECASE),
    re.compile(r"\bcommunication\b|\bteamwork\b|\bcollaboration\b|\bteamf[äa]hig", re.IGNORECASE),
)

_OPTIONAL_HINTS: tuple[str, ...] = (
    "nice-to-have",
    "nice to have",
    "ein plus",
    "wünschenswert",
    "optional",
    "preferred",
    "von vorteil",
    "pluspunkt",
    "pluspunkte",
    "wäre toll",
    "das wäre toll",
    "wäre ein plus",
    "idealerweise",
)

BulletCategory = Literal["responsibility", "requirement", "unknown"]


def _clean_bullet(text: str) -> str:
    """Strip bullet prefixes and surrounding whitespace."""

    cleaned = _BULLET_PREFIX_RE.sub("", text or "").strip()
    return re.sub(r"\s+", " ", cleaned)


def looks_like_responsibility(text: str) -> bool:
    """Return True if ``text`` resembles an action/duty statement."""

    cleaned = _clean_bullet(text).casefold()
    if not cleaned:
        return False

    normalized = cleaned
    for pronoun in ("you ", "du ", "sie ", "wir "):
        if normalized.startswith(pronoun):
            normalized = normalized[len(pronoun) :]
            break

    tokens = normalized.split()
    while tokens and tokens[0] in {"gemeinsam", "zusammen", "mit", "als"}:
        tokens = tokens[1:]
    normalized = " ".join(tokens)

    if " you will " in cleaned:
        return True
    return any(normalized.startswith(prefix) or cleaned.startswith(prefix) for prefix in _RESPONSIBILITY_PREFIXES)


def looks_like_requirement(text: str) -> bool:
    """Return True if ``text`` resembles a qualification/skill line."""

    cleaned = _clean_bullet(text)
    if not cleaned:
        return False
    lower = cleaned.casefold()
    if lower.startswith(
        (
            "you have",
            "you'll have",
            "bring",
            "must have",
            "required:",
            "du bist",
            "bist du",
            "du bringst",
            "darauf freuen wir uns",
        )
    ):
        return True
    for pattern in _REQUIREMENT_PATTERNS:
        if pattern.search(cleaned):
            return True
    return False


def categorize_bullet(text: str) -> BulletCategory:
    """Classify a bullet as responsibility or requirement using heuristics."""

    is_resp = looks_like_responsibility(text)
    is_req = looks_like_requirement(text)

    if is_req and not is_resp:
        return "requirement"
    if is_resp and not is_req:
        return "responsibility"
    if is_req and is_resp:
        return "requirement"
    return "unknown"


def classify_bullets(items: Sequence[str]) -> dict[str, list[str]]:
    """Split ``items`` into responsibilities and requirements lists."""

    responsibilities: list[str] = []
    requirements: list[str] = []
    for raw in items:
        item = _clean_bullet(raw)
        if not item:
            continue
        category = categorize_bullet(item)
        if category == "responsibility":
            responsibilities.append(item)
        elif category == "requirement":
            requirements.append(item)
        else:
            requirements.append(item)
    return {"responsibilities": responsibilities, "requirements": requirements}


def contains_optional_hint(text: str) -> bool:
    """Return True when optional/"nice to have" markers appear."""

    lower = _clean_bullet(text).casefold()
    return any(hint in lower for hint in _OPTIONAL_HINTS)
