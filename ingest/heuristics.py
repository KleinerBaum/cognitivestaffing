import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from config import ModelTask, get_model_for
from core.rules import COMMON_CITY_NAMES
from core.regexes import CITY_REGEX_IN_PATTERN, FOOTER_CONTACT_PARSE
from llm.openai_responses import build_json_schema_format, call_responses_safe
from models.need_analysis import NeedAnalysisProfile, Requirements
from nlp.entities import extract_location_entities
from utils.normalization import (
    NormalizedProfilePayload,
    extract_company_size,
    normalize_city_name,
    normalize_country,
    normalize_language_list,
    normalize_profile,
)
from utils.patterns import GENDER_SUFFIX_INLINE_RE, GENDER_SUFFIX_TRAILING_RE


HEURISTICS_LOGGER = logging.getLogger("cognitive_needs.heuristics")


def _log_heuristic_fill(field: str, rule: str, *, detail: str | None = None) -> None:
    """Emit a structured log entry describing a heuristic patch."""

    message = f"Heuristic filled {field}"
    if detail:
        message = f"{message} {detail}"
    message = f"{message} (rule: {rule})"
    extra = {
        "heuristic_field": field,
        "heuristic_rule": rule,
    }
    if detail:
        extra["heuristic_detail"] = detail
    HEURISTICS_LOGGER.info(message, extra=extra)


# Captures phrases such as "Brand, ein Unternehmen der ParentGmbH" to pull both the
# consumer brand and the legal entity. German legal forms like GmbH/AG are covered.
_BRAND_OF_RE = re.compile(
    r"([A-ZÄÖÜ][\w& ]+?),\s+ein[^,]*?\s+der\s+([A-ZÄÖÜ][\w& ]+(?:GmbH|AG|Inc|Ltd|UG|KG))",
    re.IGNORECASE,
)
# Generic legal-entity detector for standalone company names ending with GmbH, AG, Inc,
# etc., used when we only know the registered company form.
_COMPANY_FORM_RE = re.compile(
    r"\b([A-ZÄÖÜ][\w& ]+(?:GmbH|AG|Inc|Ltd|UG|KG))\b",
)
# Extracts "Wir sind Company" style introductions in German job ads.
_WE_ARE_RE = re.compile(r"wir sind\s+([A-ZÄÖÜ][\w& ]+)", re.IGNORECASE)
# Looks for explicit location hints like "Standort: Köln" or "Location - Berlin".
_CITY_HINT_RE = re.compile(
    r"(?:city|ort|location|standort|arbeitsort|einsatzort)[:\-\s]+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\s-]+)",
    re.IGNORECASE,
)
_CITY_IN_RE = re.compile(
    r"\b(?:in|bei)\s+(?:dem\s+herzen\s+von\s+|der\s+stadt\s+|der\s+metropole\s+|mitte\s+von\s+)?"
    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+){0,2})",
    re.IGNORECASE,
)
_CITY_LINE_RE = re.compile(
    r"(?im)^(?:location|standort|arbeitsort|office|büro|buero)\s*[:\-–]\s+"
    r"(?P<city>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+){0,2})",
)
_CITY_ADDRESS_RE = re.compile(
    r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß'`.-]+\s+\d+[a-zA-Z]?[,]?\s*)?"
    r"(?P<postal>\d{4,5})\s+(?P<city>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`.-]+){0,2})",
)
_COMMON_CITIES: Tuple[str, ...] = COMMON_CITY_NAMES
_COMMON_CITY_KEYS: set[str] = {city.casefold() for city in _COMMON_CITIES}

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s()\/.-]{5,}\d")
_URL_RE = re.compile(r"(?:(?:https?://|www\.)[^\s<>()]+)", re.IGNORECASE)
_NAME_RE = re.compile(r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`-]+){1,3})")
_CONTACT_KEYWORDS = (
    "your contact",
    "ansprechpartner",
    "ansprechperson",
    "kontakt",
    "kontaktperson",
    "contact",
    "hiring manager",
    "human resources",
    "hr",
    "people & culture",
    "talent acquisition",
    "recruiting",
    "recruiter",
    "personalabteilung",
    "bewerbung",
)
_HR_HINTS = (
    "hr",
    "human resources",
    "people & culture",
    "people and culture",
    "recruiting",
    "talent acquisition",
    "personal",
    "personalabteilung",
)
_CONTACT_NAME_STOPWORDS = {
    "ansprechpartner",
    "ansprechpartnerin",
    "ansprechpersonen",
    "ansprechperson",
    "kontakt",
    "kontaktperson",
    "contact",
    "hr",
    "team",
    "unsere",
    "ihre",
    "ihr",
    "dein",
    "deine",
    "liebe",
    "bewerbung",
    "acquisition",
    "culture",
    "hiring",
    "manager",
    "people",
    "recruiter",
    "recruiting",
    "talent",
}
_TEAM_STRUCTURE_PAREN_RE = re.compile(r"\(([^)]*team[^)]*)\)", re.IGNORECASE)
_TEAM_STRUCTURE_CONNECTOR_RE = re.compile(r"^(?:mit|with|in)\s+", re.IGNORECASE)
_ROLE_CONTACT_RE = re.compile(
    r"(?P<title>[A-ZÄÖÜ][^:\n]{0,80}?)\s*:\s*(?P<name>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'`-]+){0,3})(?=[\s,;|).]|$)",
)
_REPORTS_TO_RE = re.compile(r"\breport(?:s|ing)?\s+to\s+(?P<target>[^.\n]+)", re.IGNORECASE)
_REPORTING_EXCLUDE_KEYWORDS = tuple(
    {
        *(_CONTACT_KEYWORDS),
        *(_HR_HINTS),
        "ansprechpartnerin",
        "ansprechpersonen",
        "ansprechperson",
        "people partner",
        "talent manager",
        "talent managerin",
        "recruiter",
    }
)
_LEADERSHIP_KEYWORDS = (
    "leiter",
    "leitung",
    "lead",
    "manager",
    "head",
    "director",
    "chief",
    "geschäftsführer",
    "geschaeftsfuehrer",
    "geschäftsleitung",
    "bereichsleitung",
    "vorstand",
    "vp",
    "vice president",
)
_LEADERSHIP_ACRONYM_RE = re.compile(
    r"^(?:c[aitmsodpfr]{1,2}o|ceo|cto|cfo|cio|cco|cmo|cpo|cso|cro|cdo|ciso|cio|coo|cgo|cxo|vp|svp|evp|md|gm)\b",
    re.IGNORECASE,
)
_TRAVEL_SHARE_RE = re.compile(
    r"\b(?:up to|bis zu|ca\.?|around)?\s*(?P<percent>\d{1,3})\s*%\s*(?:reise(n)?|travel|reisetaetigkeit|reiseanteil)\b",
    re.IGNORECASE,
)
_TEAM_SIZE_RE = re.compile(
    r"\b(?:team\s+(?:of|von)|teamgröße\s*(?:von)?|führt?\s+ein(?:e)?\s+team\s+von)\s+(?P<count>\d{1,3})\b",
    re.IGNORECASE,
)
_DIRECT_REPORTS_RE = re.compile(
    r"\b(?P<count>\d{1,3})\+?\s*(?:direct\s+reports?|reports?|mitarbeiter(?:innen)?|people)\b",
    re.IGNORECASE,
)

_INVALID_CITY_KEYWORDS: Tuple[str, ...] = (
    "remote",
    "hybrid",
    "home office",
    "home-office",
    "homeoffice",
    "work from home",
    "working from home",
    "flexible arbeitszeit",
    "flexible arbeitszeiten",
    "arbeitszeit",
    "arbeitszeiten",
    "working hour",
    "working hours",
    "work schedule",
    "flexible working hours",
    "flexible working hour",
    "deutschland",
    "germany",
    "österreich",
    "austria",
    "schweiz",
    "switzerland",
    "europa",
    "europe",
)
_INVALID_CITY_SUFFIXES: Tuple[str, ...] = ("zeiten", "hours")
_CITY_TRAILING_STOPWORDS = {
    "flexible",
    "arbeitszeit",
    "arbeitszeiten",
    "vollzeit",
    "teilzeit",
    "remote",
    "hybrid",
    "benefits",
    "homeoffice",
    "home-office",
    "home",
    "office",
    "working",
    "hours",
}

BENEFIT_LEXICON: dict[str, str] = {
    "flexible arbeitszeiten": "Flexible Arbeitszeiten",
    "flexible arbeitszeit": "Flexible Arbeitszeiten",
    "mobiles arbeiten": "Mobiles Arbeiten",
    "mobile working": "Mobiles Arbeiten",
    "betriebliche altersvorsorge": "Betriebliche Altersvorsorge",
    "company pension": "Betriebliche Altersvorsorge",
    "retirement plan": "Betriebliche Altersvorsorge",
    "pension": "Betriebliche Altersvorsorge",
    "jobticket": "Jobticket",
    "hybrides arbeiten": "Hybrides Arbeiten",
    "remote work": "Remote Work",
    "homeoffice": "Homeoffice",
    "home office": "Homeoffice",
    "home-office": "Homeoffice",
    "health insurance": "Health Insurance",
    "medical insurance": "Health Insurance",
    "private health insurance": "Health Insurance",
    "dental insurance": "Dental Insurance",
    "vision insurance": "Vision Insurance",
    "insurance": "Insurance",
    "401k": "401(k)",
    "401(k)": "401(k)",
    "paid time off": "Paid Time Off",
    "pto": "Paid Time Off",
    "vacation days": "Vacation Days",
    "urlaubstage": "Urlaubstage",
    "30 tage urlaub": "30 Tage Urlaub",
    "30 days vacation": "30 Days Vacation",
    "free drinks": "Free Drinks",
    "free snacks": "Free Snacks",
    "fruit basket": "Fresh Fruit",
    "gym membership": "Gym Membership",
    "fitnessstudio": "Gym Membership",
    "bonus": "Bonus",
    "annual bonus": "Annual Bonus",
    "training budget": "Training Budget",
    "learning budget": "Training Budget",
    "education allowance": "Training Budget",
    "conference budget": "Conference Budget",
    "professional development": "Professional Development",
    "weiterbildung": "Weiterbildung",
}

_CITY_FIX_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "Primary city name without prefixes, suffixes, or country information.",
        }
    },
    "required": ["city"],
}


@dataclass(slots=True)
class _ContactCandidate:
    """Normalized candidate for a company contact extracted from raw text."""

    name: str
    email: str | None
    phone: str | None
    line_index: int
    hr_score: int
    label_score: int
    email_score: int
    phone_score: int


def _tokenize_name(name: str) -> list[str]:
    """Return significant lowercase tokens for ``name`` suitable for matching."""

    tokens = [part for part in re.split(r"[\s-]+", name) if part]
    normalized: list[str] = []
    for token in tokens:
        lowered = token.casefold()
        if len(lowered) < 2:
            continue
        if lowered in _CONTACT_NAME_STOPWORDS:
            continue
        normalized.append(lowered)
    return normalized


def _email_matches_name(email: str, name: str) -> bool:
    """Return ``True`` if ``email`` appears to belong to ``name``."""

    if not email or not name:
        return False
    local_part = email.split("@", 1)[0].casefold()
    tokens = _tokenize_name(name)
    return any(token and token in local_part for token in tokens if len(token) >= 3)


def _normalize_phone(raw: str) -> str:
    """Return ``raw`` stripped of trailing punctuation and normalized spacing."""

    cleaned = raw.strip().rstrip(".,;)")
    return re.sub(r"\s+", " ", cleaned)


def _collect_emails(lines: Sequence[str]) -> list[tuple[str, int]]:
    """Return list of emails with their source line indices."""

    results: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        for match in _EMAIL_RE.finditer(line):
            results.append((match.group(0).lower(), idx))
    return results


def _collect_phones(lines: Sequence[str]) -> list[tuple[str, int]]:
    """Return list of phone numbers with their source line indices."""

    results: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        for match in _PHONE_RE.finditer(line):
            candidate = _normalize_phone(match.group(0))
            digits = re.sub(r"\D", "", candidate)
            if len(digits) < 6:
                continue
            results.append((candidate, idx))
    return results


def _find_best_email(
    tokens: Sequence[str],
    line_index: int,
    emails: Sequence[tuple[str, int]],
    *,
    max_distance: int = 6,
) -> tuple[str | None, int]:
    """Return the most plausible email for a contact name."""

    best_email: str | None = None
    best_score = 0
    for email, idx in emails:
        distance = abs(idx - line_index)
        if distance > max_distance:
            continue
        local_part = email.split("@", 1)[0]
        matches = sum(1 for token in tokens if len(token) >= 3 and token in local_part)
        score = matches * 5
        if matches:
            score += 3
        if distance <= 1:
            score += 3
        elif distance <= 3:
            score += 1
        score -= distance
        if matches == 0 and distance > 2:
            continue
        if score > best_score:
            best_score = score
            best_email = email
    return best_email, best_score


def _find_best_phone(
    line_index: int,
    phones: Sequence[tuple[str, int]],
    *,
    max_distance: int = 6,
) -> tuple[str | None, int]:
    """Return the most relevant phone number near ``line_index``."""

    best_phone: str | None = None
    best_score = 0
    for phone, idx in phones:
        distance = abs(idx - line_index)
        if distance > max_distance:
            continue
        digits = re.sub(r"\D", "", phone)
        score = max(0, 6 - distance) + min(len(digits), 14)
        if score > best_score:
            best_score = score
            best_phone = phone
    return best_phone, best_score


def _extract_generic_contact_details(text: str) -> tuple[str | None, str | None]:
    """Return the first email and phone number found in ``text``."""

    email_match = _EMAIL_RE.search(text)
    phone_match = _PHONE_RE.search(text)
    email = email_match.group(0).lower() if email_match else None
    phone = _normalize_phone(phone_match.group(0)) if phone_match else None
    if phone:
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 6:
            phone = None
    return email, phone


def _extract_travel_share(text: str) -> int | None:
    """Return an integer travel percentage if present in ``text``."""

    for match in _TRAVEL_SHARE_RE.finditer(text):
        value = int(match.group("percent"))
        if 0 < value <= 100:
            return value
    return None


def _extract_team_size(text: str) -> int | None:
    """Return a detected team size from ``text``."""

    for match in _TEAM_SIZE_RE.finditer(text):
        value = int(match.group("count"))
        if value > 0:
            return value
    return None


def _extract_direct_reports(text: str) -> int | None:
    """Return the number of direct reports mentioned in ``text``."""

    for match in _DIRECT_REPORTS_RE.finditer(text):
        value = int(match.group("count"))
        if value > 0:
            return value
    return None


def _paragraphs_with_indices(lines: Sequence[str]) -> list[list[tuple[int, str]]]:
    """Return paragraphs retaining the original line indices."""

    paragraphs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if line.strip():
            current.append((idx, line))
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _contact_rank(candidate: _ContactCandidate) -> tuple[int, int, int, int, int]:
    """Sorting key to prioritise reliable contact candidates."""

    return (
        -candidate.hr_score,
        -candidate.label_score,
        -candidate.email_score,
        -candidate.phone_score,
        candidate.line_index,
    )


def _is_viable_contact_name(name: str) -> bool:
    """Return ``True`` if ``name`` looks like a person rather than a label."""

    tokens = _tokenize_name(name)
    return len(tokens) >= 2


def _collect_local_context(
    paragraph: Sequence[tuple[int, str]],
    target_index: int,
    *,
    window: int = 2,
) -> str:
    """Return lowercased context around ``target_index`` within ``paragraph``."""

    parts: list[str] = []
    for line_idx, content in paragraph:
        if abs(line_idx - target_index) <= window:
            parts.append(content)
    return " ".join(parts).casefold()


def _extract_footer_contact_details(text: str) -> dict[str, str | None]:
    """Return structured footer contact details if present in ``text``."""

    match = FOOTER_CONTACT_PARSE.search(text)
    if not match:
        return {}
    details: dict[str, str | None] = {}
    hr_name = (match.group("hr") or "").strip()
    manager_name = (match.group("mgr") or "").strip()
    if hr_name:
        details["hr_name"] = hr_name
    if manager_name:
        details["manager_name"] = manager_name
    raw_segment = match.group(0)
    emails = [email.group(0).lower() for email in _EMAIL_RE.finditer(raw_segment)]
    hr_email: str | None = None
    if hr_name:
        tokens = [token for token in _tokenize_name(hr_name) if len(token) >= 3]
    else:
        tokens = []
    for email in emails:
        local_part = email.split("@", 1)[0]
        if any(token in local_part for token in tokens):
            hr_email = email
            break
    if hr_email is None and emails:
        hr_email = emails[-1]
    if hr_email:
        details["hr_email"] = hr_email
    phone = match.group("phone")
    if phone:
        details["phone"] = _normalize_phone(phone)
    website = match.group("website")
    if website:
        details["website"] = website.strip()
    return details


def _extract_contact_candidates(text: str) -> list[_ContactCandidate]:
    """Return a list of potential company contacts extracted from ``text``."""

    lines = text.splitlines()
    emails = _collect_emails(lines)
    phones = _collect_phones(lines)
    paragraphs = _paragraphs_with_indices(lines)
    candidates: dict[str, _ContactCandidate] = {}

    paragraph_line_lengths: dict[int, int] = {}
    for paragraph in paragraphs:
        paragraph_text = "\n".join(line for _, line in paragraph)
        paragraph_lower = paragraph_text.casefold()
        distance_limit = max(3, min(6, len(paragraph)))
        for line_index, _ in paragraph:
            paragraph_line_lengths[line_index] = distance_limit
        if not any(keyword in paragraph_lower for keyword in _CONTACT_KEYWORDS):
            continue
        for line_index, line in paragraph:
            for match in _NAME_RE.finditer(line):
                name = match.group(0).strip()
                if not _is_viable_contact_name(name):
                    continue
                tokens = _tokenize_name(name)
                if not tokens:
                    continue
                context_lower = _collect_local_context(paragraph, line_index)
                hr_score = sum(1 for hint in _HR_HINTS if hint in context_lower)
                label_score = 0
                if "ansprechpartner" in context_lower or "ansprechperson" in context_lower:
                    label_score += 2
                if "kontakt" in context_lower or "contact" in context_lower:
                    label_score += 1
                email, email_score = _find_best_email(tokens, line_index, emails, max_distance=distance_limit)
                phone, phone_score = _find_best_phone(line_index, phones, max_distance=distance_limit)
                if hr_score == 0 and label_score == 0 and email_score == 0 and phone_score == 0:
                    continue
                candidate = _ContactCandidate(
                    name=name,
                    email=email,
                    phone=phone,
                    line_index=line_index,
                    hr_score=hr_score,
                    label_score=label_score,
                    email_score=email_score,
                    phone_score=phone_score,
                )
                key = name.casefold()
                previous = candidates.get(key)
                if previous is None or _contact_rank(candidate) < _contact_rank(previous):
                    candidates[key] = candidate

    for line_index, line in enumerate(lines):
        for match in _ROLE_CONTACT_RE.finditer(line):
            title = _normalize_role_title(match.group("title"))
            name = match.group("name").strip()
            if not title or not name:
                continue
            if not _NAME_RE.fullmatch(name):
                continue
            lowered_title = title.casefold()
            if not any(keyword in lowered_title for keyword in _REPORTING_EXCLUDE_KEYWORDS):
                continue
            if not _is_viable_contact_name(name):
                continue
            tokens = _tokenize_name(name)
            if not tokens:
                continue
            paragraph_window = paragraph_line_lengths.get(line_index, 6)
            context_lower = line.casefold()
            hr_score = max(
                1,
                sum(1 for hint in _HR_HINTS if hint in lowered_title or hint in context_lower),
            )
            label_score = 1 if any(keyword in lowered_title for keyword in _CONTACT_KEYWORDS) else 0
            email, email_score = _find_best_email(tokens, line_index, emails, max_distance=paragraph_window)
            phone, phone_score = _find_best_phone(line_index, phones, max_distance=paragraph_window)
            if hr_score == 0 and label_score == 0 and email_score == 0 and phone_score == 0:
                continue
            candidate = _ContactCandidate(
                name=name,
                email=email,
                phone=phone,
                line_index=line_index,
                hr_score=hr_score,
                label_score=label_score,
                email_score=email_score,
                phone_score=phone_score,
            )
            key = name.casefold()
            previous = candidates.get(key)
            if previous is None or _contact_rank(candidate) < _contact_rank(previous):
                candidates[key] = candidate

    ordered = sorted(candidates.values(), key=_contact_rank)
    if ordered:
        return ordered

    # Fallback: attempt to pair the most name-like line with an adjacent email if
    # no labelled contact section was found.
    for idx, line in enumerate(lines):
        for match in _NAME_RE.finditer(line):
            name = match.group(0).strip()
            if not _is_viable_contact_name(name):
                continue
            tokens = _tokenize_name(name)
            if not tokens:
                continue
            email, email_score = _find_best_email(tokens, idx, emails)
            if not email:
                continue
            phone, phone_score = _find_best_phone(idx, phones)
            candidate = _ContactCandidate(
                name=name,
                email=email,
                phone=phone,
                line_index=idx,
                hr_score=0,
                label_score=0,
                email_score=email_score,
                phone_score=phone_score,
            )
            return [candidate]
    return []


def _clean_team_phrase(raw: str) -> str:
    """Return ``raw`` stripped of bullets, connectors, and trailing punctuation."""

    cleaned = raw.strip()
    cleaned = re.sub(r"^[•*·\-\u2022\u2023\u2043\u25E6\u2219\u204C\u204D\u00B7\s]+", "", cleaned)
    cleaned = _TEAM_STRUCTURE_CONNECTOR_RE.sub("", cleaned)
    cleaned = cleaned.strip(" ,.;:!?–—-")
    return re.sub(r"\s+", " ", cleaned)


def _extract_team_structure(text: str) -> str:
    """Return a concise description of the team setup from ``text`` if found."""

    if not text:
        return ""

    for match in _TEAM_STRUCTURE_PAREN_RE.finditer(text):
        candidate = _clean_team_phrase(match.group(1))
        if candidate and len(candidate) <= 180:
            return candidate

    segments = re.split(r"[\n.;]", text)
    for segment in segments:
        if "team" not in segment.casefold():
            continue
        candidate = _clean_team_phrase(segment)
        if candidate:
            if len(candidate) > 200:
                candidate = candidate[:200].rstrip(" ,.;:")
            return candidate
    return ""


def _normalize_role_title(raw: str) -> str:
    """Return ``raw`` trimmed of bullets and extra whitespace."""

    cleaned = re.sub(r"^[•*·\-\u2022\s]+", "", raw.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,.;:!?")


def _is_reporting_title_excluded(title_lower: str) -> bool:
    """Return ``True`` if ``title_lower`` refers to HR/contact personnel."""

    return any(keyword in title_lower for keyword in _REPORTING_EXCLUDE_KEYWORDS)


def _is_leadership_title(title: str) -> bool:
    """Return ``True`` if ``title`` appears to denote a leadership role."""

    normalized = re.sub(r"\(.*?\)", "", title).casefold()
    normalized = normalized.replace("-", " ")
    if _LEADERSHIP_ACRONYM_RE.match(normalized):
        return True
    return any(keyword in normalized for keyword in _LEADERSHIP_KEYWORDS)


def _extract_reporting_line(text: str) -> tuple[str, str]:
    """Return reporting line title and manager name inferred from ``text``."""

    if not text:
        return "", ""

    reports_match = _REPORTS_TO_RE.search(text)
    if reports_match:
        target = reports_match.group("target").strip()
        if target:
            reporting_line = re.sub(r"\s+", " ", target).strip(" .;:,")
            manager_name = ""
            name_match = _NAME_RE.search(reporting_line)
            if name_match:
                manager_name = name_match.group(1).strip()
                title_candidate = re.sub(
                    r"\(\s*" + re.escape(manager_name) + r"\s*\)",
                    "",
                    reporting_line,
                )
                if title_candidate == reporting_line:
                    title_candidate = reporting_line.replace(manager_name, "")
                title_candidate = re.sub(r"\s{2,}", " ", title_candidate).strip(" ,;-()")
                if title_candidate:
                    reporting_line = title_candidate
            return reporting_line, manager_name

    candidates: list[tuple[int, str, str]] = []
    fallback: list[tuple[int, str, str]] = []

    for match in _ROLE_CONTACT_RE.finditer(text):
        title = _normalize_role_title(match.group("title"))
        name = match.group("name").strip()
        if not title or not name:
            continue
        if not _NAME_RE.fullmatch(name):
            continue
        lowered_title = title.casefold()
        if _is_reporting_title_excluded(lowered_title):
            continue
        bucket = candidates if _is_leadership_title(title) else fallback
        bucket.append((match.start(), title, name))

    if candidates:
        _, title, name = min(candidates, key=lambda item: item[0])
        return title, name
    if fallback:
        _, title, name = min(fallback, key=lambda item: item[0])
        return title, name
    return "", ""


def _extract_company_website(text: str) -> str | None:
    """Return the first plausible website URL from ``text``."""

    for match in _URL_RE.finditer(text):
        url = match.group(0).strip()
        if "@" in url:
            continue
        cleaned = url.rstrip('.,;)"')
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered.startswith("www."):
            normalized = f"https://{cleaned}"
        elif lowered.startswith(("http://", "https://")):
            normalized = cleaned
        else:
            normalized = f"https://{cleaned}"
        return normalized
    return None


def _clean_city_candidate(city: str | None) -> str:
    """Return the first non-empty line of ``city`` stripped of whitespace."""

    if not city:
        return ""
    cleaned = city.splitlines()[0].strip()
    return cleaned.rstrip(",.;:")


def _trim_city_stopwords(city: str) -> str:
    """Return ``city`` without trailing stop words that are not part of a place name."""

    tokens = [token for token in city.split() if token]
    if not tokens:
        return city
    trimmed: list[str] = []
    for token in tokens:
        normalized = token.strip(",.;:").casefold()
        if normalized in _CITY_TRAILING_STOPWORDS:
            break
        trimmed.append(token.strip(",.;:"))
    if not trimmed:
        return city
    return " ".join(trimmed).strip()


def _canonicalize_city_name(city: str) -> str:
    """Return ``city`` normalised to a known common city when possible."""

    lowered = city.casefold()
    for known_city in _COMMON_CITIES:
        if known_city.casefold() == lowered:
            return known_city
        prefix = known_city.casefold()
        if lowered.startswith(f"{prefix} ") or lowered.startswith(f"{prefix}-") or lowered.startswith(f"{prefix}/"):
            return known_city
    return city


def _city_value_is_invalid(city: str | None) -> str | None:
    """Return the marker that deems ``city`` invalid or ``None`` if it looks fine."""

    if not city:
        return None
    normalized = city.strip()
    if not normalized:
        return None
    lowered = normalized.casefold()
    for keyword in _INVALID_CITY_KEYWORDS:
        if keyword in lowered:
            return keyword
    for suffix in _INVALID_CITY_SUFFIXES:
        if lowered.endswith(suffix):
            return suffix
    return None


def _city_candidate_is_plausible(city: str) -> bool:
    """Return ``True`` if ``city`` appears to be a real geographic location."""

    if not city:
        return False
    if _benefit_label_for_phrase(city):
        return False
    marker = _city_value_is_invalid(city)
    if marker:
        return False
    tokens = [token for token in re.split(r"[\s-]+", city) if token]
    if not tokens:
        return False
    if any(token.isdigit() for token in tokens):
        return False
    if not any(token[0].isalpha() for token in tokens):
        return False
    return True


def _city_value_suits_work_schedule(city: str | None) -> bool:
    """Return ``True`` if ``city`` contains hints about work schedule details."""

    if not city:
        return False
    lowered = city.casefold()
    return "arbeitszeit" in lowered or "working hour" in lowered or lowered.endswith("zeiten")


def _city_candidate_is_trustworthy(city: str, text: str, regex_hint: str) -> bool:
    """Return ``True`` if ``city`` looks like a reliable location candidate."""

    normalized = city.strip()
    if not normalized:
        return False
    lowered = normalized.casefold()
    if regex_hint and lowered == regex_hint.casefold():
        return True
    if lowered in _COMMON_CITY_KEYS:
        return True
    match = _CITY_HINT_RE.search(text)
    if match:
        hint = match.group(1).split("|")[0].split(",")[0].strip()
        if hint and lowered == hint.casefold():
            return True
    return False


_LOCATION_KEYWORDS = {
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "on site",
    "vor ort",
    "büro",
    "office",
    "germany",
    "deutschland",
    "austria",
    "österreich",
    "switzerland",
    "schweiz",
    "europe",
    "europa",
    "bavaria",
    "bayern",
    "nrw",
}

_LOCATION_KEYWORD_NORMALIZED = {re.sub(r"[\W_]+", "", keyword).casefold() for keyword in _LOCATION_KEYWORDS}

_JOB_TYPE_MAP = {
    "apprenticeship": [
        "ausbildung",
        "auszubildende",
        "auszubildender",
        "auszubildenden",
        "azubi",
        "lehre",
        "apprentice",
        "apprenticeship",
    ],
    "trainee_program": [
        "trainee",
        "traineeprogramm",
        "trainee-programm",
        "traineeship",
        "graduate program",
        "graduate-programm",
    ],
    "working_student": [
        "werkstudent",
        "werkstudentin",
        "werkstudent*",
        "werkstudent:in",
        "working student",
    ],
    "internship": ["praktikum", "internship"],
    "full_time": ["vollzeit", "full-time", "full time"],
    "part_time": ["teilzeit", "part-time", "part time"],
}

_CONTRACT_TYPE_MAP = {
    "permanent": ["festanstellung", "permanent", "unbefristet"],
    "fixed_term": ["befristet", "fixed-term", "temporary"],
    "freelance": ["freelance", "freelancer", "contractor", "selbstständig"],
}

_WORK_POLICY_MAP = {
    "remote": [
        "remote",
        "home office",
        "home-office",
        "homeoffice",
        "remote-first",
        "remote first",
        "fully remote",
        "work from home",
        "work-from-home",
        "work from anywhere",
        "work-from-anywhere",
        "work anywhere",
        "work-anywhere",
        "location independent",
        "mobile work",
        "mobiles arbeiten",
        "ortsunabhängig",
    ],
    "hybrid": ["hybrid", "teilremote", "teil-remote", "mixed remote", "flexible work"],
    "onsite": [
        "vor ort",
        "onsite",
        "on-site",
        "im büro",
        "office-first",
        "büropräsenz",
    ],
}

# Picks up remote work percentages like "80 % remote" or "50 Prozent Home-Office",
# accounting for German spelling of percent.
_REMOTE_PERCENT_RE = re.compile(
    r"(\d{1,3})\s*(?:%|prozent)\s*(?:remote|home[-\s]*office|mobile(?:s)?\s+arbeiten?)",
    re.IGNORECASE,
)
# Detects patterns such as "3 Tage/Woche im Büro" including numeric ranges (e.g. 2-3)
# to estimate hybrid office attendance.
_REMOTE_DAYS_OFFICE_RE = re.compile(
    r"(?:(?P<min>\d{1,2})[–-](?P<max>\d{1,2})|(?P<single>\d{1,2}))\s*"
    r"(?:Tag(?:e)?|day(?:s)?)\s*/\s*Woche[^\n]*?(?:im\s+(?:Office|Büro|HQ)|vor\s+Ort)",
    re.IGNORECASE,
)
# Similar to _REMOTE_DAYS_OFFICE_RE but focused on "remote" or "Home Office" mentions
# so we can gauge remote days per week.
_REMOTE_DAYS_REMOTE_RE = re.compile(
    r"(?:(?P<min>\d{1,2})[–-](?P<max>\d{1,2})|(?P<single>\d{1,2}))\s*"
    r"(?:Tag(?:e)?|day(?:s)?)"
    r"(?:\s*(?:/|pro|per)\s*(?:Woche|week))?[^\n]*?"
    r"(?:remote|Home[-\s]*Office|von\s+zu\s+Hause|work\s+from\s+home|work\s+from\s+anywhere|"
    r"mobile\s+work|mobiles?\s+Arbeiten?)",
    re.IGNORECASE,
)

_DATE_PATTERNS = [
    r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    r"\b(\d{4}-\d{2}-\d{2})\b",
]

# Maps season labels like "Sommer 2025" to approximate months, covering English and
# German spellings.
_SEASON_RE = re.compile(
    r"(Frühling|Frühjahr|Sommer|Herbst|Autumn|Fall|Winter)\s+(\d{4})",
    re.IGNORECASE,
)
_SEASON_MONTH = {
    "frühling": 3,
    "frühjahr": 3,
    "spring": 3,
    "sommer": 6,
    "summer": 6,
    "herbst": 9,
    "fall": 9,
    "autumn": 9,
    "winter": 12,
}

# Identifies immediate start phrases ("ab sofort", "ASAP", etc.) to normalise start
# dates.
_IMMEDIATE_RE = re.compile(
    r"(ab\s+sofort|zum\s+nächstmöglichen\s+zeitpunkt|zum\s+frühestmöglichen\s+zeitpunkt|"
    r"asap|as\s+soon\s+as\s+possible|immediately)",
    re.IGNORECASE,
)

# Catches salary ranges such as "50.000 - 60.000 €" or "45k–55k eur". Handles dotted
# thousands, spaces, and "k" suffix shorthand.
_SALARY_RANGE_RE = re.compile(
    r"(\d[\d.,\s]*(?:k)?)\s*(?:[-–]|bis)\s*(\d[\d.,\s]*(?:k)?)\s*(?:€|eur|euro)",
    re.IGNORECASE,
)
# Matches single salary mentions with flexible currency placement ("€70k" or "70.000 EUR").
_SALARY_SINGLE_RE = re.compile(
    r"(?:€|eur|euro)\s*(\d[\d.,\s]*(?:k)?)|(\d[\d.,\s]*(?:k)?)\s*(?:€|eur|euro)",
    re.IGNORECASE,
)
# Looks for bonus percentages like "20% Bonus" but avoids general percentages by
# requiring explicit bonus vocabulary.
_BONUS_PERCENT_RE = re.compile(r"(\d{1,3})\s*%\s*(?:variable|bonus)", re.IGNORECASE)
# Grabs descriptive commission phrases so we can surface text snippets about variable
# compensation structures.
_BONUS_TEXT_RE = re.compile(
    r"(?:bonus|provision|pr[aä]mie|commission)[^\n]*",
    re.IGNORECASE,
)

_POSTAL_CODE_RE = re.compile(r"\b\d{4,5}\b")

# Requirement extraction helpers
_REQ_REQUIRED_HEADINGS = {
    "anforderungen",
    "dein profil",
    "ihr profil",
    "must-haves",
    "must have",
    "must haves",
    "requirements",
    "qualifications",
    "qualifikationen",
    "deine qualifikationen",
    "anforderungsprofil",
    "dein anforderungsprofil",
    "unser anforderungsprofil",
    "skills & experience",
    "was du mitbringst",
    "was sie mitbringen",
    "was wir erwarten",
    "what you bring",
}
_REQ_OPTIONAL_HEADINGS = {
    "nice-to-haves",
    "nice to have",
    "optional",
    "wünschenswert",
    "von vorteil",
    "was wir uns wünschen",
    "deine pluspunkte",
    "pluspunkte",
    "das wäre toll",
    "wäre toll",
    "wäre ein plus",
    "idealerweise",
    "idealerweise bringst du mit",
}
_OPTIONAL_HINTS = {
    "nice-to-have",
    "nice to have",
    "ein plus",
    "wünschenswert",
    "optional",
    "von vorteil",
    "pluspunkt",
    "pluspunkte",
    "wäre toll",
    "das wäre toll",
    "wäre ein plus",
    "idealerweise",
}
_SOFT_SKILL_KEYWORDS = {
    "communication",
    "kommunikation",
    "team",
    "collabor",
    "leadership",
    "analytical",
    "analytisch",
    "organised",
    "organized",
    "struktur",
    "problem",
    "begeister",
    "enthusias",
    "leidenschaft",
}
_LANGUAGE_MAP = {
    "English": ["english", "englisch"],
    "German": ["german", "deutsch"],
    "French": ["french", "französisch"],
    "Spanish": ["spanish", "spanisch"],
    "Arabic": ["arabic", "arabisch"],
    "Chinese": ["chinese", "mandarin", "mandarin chinese", "cantonese", "putonghua", "中文"],
    "Czech": ["czech", "tschechisch", "cesky", "česky", "čeština"],
    "Danish": ["danish", "dänisch"],
    "Dutch": ["dutch", "niederländisch", "holländisch"],
    "Finnish": ["finnish", "finnisch"],
    "Hindi": ["hindi"],
    "Italian": ["italian", "italienisch"],
    "Norwegian": ["norwegian", "norwegisch"],
    "Polish": ["polish", "polnisch"],
    "Portuguese": ["portuguese", "portugiesisch", "português"],
    "Russian": ["russian", "russisch"],
    "Swedish": ["swedish", "schwedisch"],
    "Turkish": ["turkish", "türkisch"],
}
_TECH_KEYWORD_CATEGORIES: Dict[str, str] = {
    ".net": "framework",
    "airflow": "tool",
    "angular": "framework",
    "ansible": "tool",
    "asp.net": "framework",
    "aws": "cloud",
    "azure": "cloud",
    "c#": "language",
    "c++": "language",
    "confluence": "tool",
    "cpp": "language",
    "css": "language",
    "django": "framework",
    "docker": "tool",
    "dotnet": "framework",
    "faiss": "tool",
    "flask": "framework",
    "gcp": "cloud",
    "git": "tool",
    "gitlab": "tool",
    "go": "language",
    "golang": "language",
    "graphql": "language",
    "hadoop": "tool",
    "html": "language",
    "java": "language",
    "javascript": "language",
    "jenkins": "tool",
    "jira": "tool",
    "js": "language",
    "kotlin": "language",
    "kubernetes": "tool",
    "mysql": "tool",
    "next.js": "framework",
    "node": "framework",
    "node.js": "framework",
    "numpy": "tool",
    "php": "language",
    "postgres": "tool",
    "postgresql": "tool",
    "power bi": "tool",
    "python": "language",
    "pytorch": "tool",
    "r": "language",
    "react": "framework",
    "react.js": "framework",
    "redis": "tool",
    "rust": "language",
    "salesforce": "tool",
    "scala": "language",
    "scikit-learn": "tool",
    "sklearn": "tool",
    "snowflake": "tool",
    "spark": "tool",
    "spring": "framework",
    "sql": "language",
    "swift": "language",
    "tableau": "tool",
    "terraform": "tool",
    "typescript": "language",
    "vue": "framework",
}
_TECH_KEYWORD_VARIANTS: Dict[str, Set[str]] = {
    ".net": {".net", "asp.net", "asp net"},
    "airflow": {"airflow"},
    "angular": {"angular"},
    "ansible": {"ansible"},
    "asp.net": {"asp.net", "asp net"},
    "aws": {"aws", "amazon web services"},
    "azure": {"azure"},
    "c#": {"c#", "c sharp", "c-sharp"},
    "c++": {"c++", "cplusplus"},
    "confluence": {"confluence"},
    "cpp": {"cpp"},
    "css": {"css"},
    "django": {"django"},
    "docker": {"docker"},
    "dotnet": {"dotnet", "net core", "netcore"},
    "faiss": {"faiss"},
    "flask": {"flask"},
    "gcp": {"gcp", "google cloud", "google cloud platform"},
    "git": {"git"},
    "gitlab": {"gitlab"},
    "go": {"go"},
    "golang": {"golang"},
    "graphql": {"graphql"},
    "hadoop": {"hadoop"},
    "html": {"html"},
    "java": {"java"},
    "javascript": {"javascript"},
    "jenkins": {"jenkins"},
    "jira": {"jira"},
    "js": {"js"},
    "kotlin": {"kotlin"},
    "kubernetes": {"kubernetes", "k8s"},
    "mysql": {"mysql"},
    "next.js": {"next.js", "nextjs"},
    "node": {"node"},
    "node.js": {"node.js", "nodejs"},
    "numpy": {"numpy"},
    "php": {"php"},
    "postgres": {"postgres"},
    "postgresql": {"postgresql"},
    "power bi": {"power bi"},
    "python": {"python"},
    "pytorch": {"pytorch"},
    "r": {"r"},
    "react": {"react"},
    "react.js": {"react.js", "reactjs"},
    "redis": {"redis"},
    "rust": {"rust"},
    "salesforce": {"salesforce"},
    "scala": {"scala"},
    "scikit-learn": {"scikit-learn"},
    "sklearn": {"sklearn"},
    "snowflake": {"snowflake"},
    "spark": {"spark", "pyspark"},
    "spring": {"spring", "spring boot", "springboot"},
    "sql": {"sql"},
    "swift": {"swift"},
    "tableau": {"tableau"},
    "terraform": {"terraform"},
    "typescript": {"typescript"},
    "vue": {"vue", "vue.js", "vuejs"},
}
_TECH_KEYWORDS = {tech for tech, category in _TECH_KEYWORD_CATEGORIES.items() if category == "tool"}
_CERT_RE = re.compile(
    r"\b([A-Za-z0-9 .()+/\-]*?(?:certification|certificate|Zertifikat|Zertifizierung)[^\n,;]*)",
    re.IGNORECASE,
)

# Responsibility extraction helpers
_BULLET_CHARS = set("•-–—*▪◦●·▶▷▸»✓→➤")
_RESP_HEADINGS = {
    "aufgabengebiet",
    "aufgaben",
    "dein spielfeld",
    "deine aufgaben",
    "deine mission",
    "jobbeschreibung",
    "hauptaufgaben",
    "ihre aufgaben",
    "ihre verantwortlichkeiten",
    "key responsibilities",
    "main tasks",
    "responsibilities",
    "tätigkeitsbeschreibung",
    "was dich bei uns erwartet",
    "was dich erwartet",
    "your responsibilities",
    "your tasks",
    "what you will do",
    "what you'll do",
    "duties",
}

_RESPONSIBILITY_STARTERS: tuple[str, ...] = (
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
    "analysierst",
    "planst",
    "führst",
    "betreust",
    "koordinierst",
    "unterstützt",
    "du ",
    "sie ",
    "wir ",
)

_SKILL_TAIL_RE = re.compile(
    r"(?:with|using|leveraging|including|incl\.?|mit|unter (?:einsatz|nutzung) von|"
    r"erfahrung mit|erfahrung in|kenntnisse in|knowledge of|expertise in)\s+([^.;\n]+)",
    re.IGNORECASE,
)


_BENEFIT_HEADINGS = {
    "benefits",
    "benefit",
    "unsere benefits",
    "deine benefits",
    "wir bieten",
    "our benefits",
    "our benefits and perks",
    "our offer",
    "our offers",
    "our perks",
    "perks",
    "benefits and perks",
    "perks & benefits",
    "perks and benefits",
    "what we offer",
    "what we provide",
    "what you get",
    "why you will love working here",
    "why you'll love working here",
    "why you’ll love working here",
    "was wir bieten",
    "was wir dir bieten",
    "was wir ihnen bieten",
    "unsere vorteile",
    "deine vorteile",
    "vorteile",
    "leistungen",
    "unser angebot",
    "angebote",
}

_BENEFIT_SEP_RE = re.compile(r"[•·∙,;\n]+")


def _is_bullet_line(line: str) -> bool:
    """Return True if ``line`` begins with a bullet or enumerator."""
    stripped = line.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    if first in _BULLET_CHARS:
        return True
    return bool(re.match(r"^\d+[.)]\s*", stripped))


def _clean_bullet(line: str) -> str:
    """Strip bullet markers and surrounding whitespace from ``line``."""
    stripped = line.lstrip()
    stripped = re.sub(r"^\d+[.)]\s*", "", stripped)
    stripped = stripped.lstrip("".join(_BULLET_CHARS))
    return stripped.strip()


def _normalize_benefit_entries(values: List[str]) -> List[str]:
    """Return a deduplicated, trimmed list of benefit entries."""

    normalized: List[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = re.sub(r"\s+", " ", raw).strip(" -–—•·\t")
        cleaned = cleaned.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(cleaned)
    return normalized


def _benefit_label_for_phrase(phrase: str) -> str | None:
    """Return canonical benefit label for ``phrase`` if known."""

    key = re.sub(r"\s+", " ", phrase.strip()).casefold()
    return BENEFIT_LEXICON.get(key)


def _extract_benefits_from_lexicon(text: str) -> List[str]:
    """Return benefit entries detected via :data:`BENEFIT_LEXICON`."""

    lowered = text.casefold()
    matches: list[str] = []
    for marker, label in BENEFIT_LEXICON.items():
        if marker in lowered:
            matches.append(label)
    return _normalize_benefit_entries(matches)


def _match_benefit_heading(line: str) -> Tuple[bool, str]:
    """Return ``(True, trailing)`` if ``line`` is a benefit heading."""

    stripped = line.strip()
    if not stripped:
        return False, ""

    cleaned = _clean_bullet(stripped)
    normalized = re.sub(r"\s+", " ", cleaned).strip(" -–—•\t")
    if not normalized:
        return False, ""

    parts = re.split(r"[:：]", normalized, maxsplit=1)
    heading_norm = re.sub(r"\s+", " ", parts[0]).strip(" -–—•\t").lower()
    if heading_norm in _BENEFIT_HEADINGS:
        trailing = parts[1].strip() if len(parts) > 1 else ""
        return True, trailing

    lowered = normalized.lower()
    for heading in _BENEFIT_HEADINGS:
        if not lowered.startswith(heading):
            continue
        remainder = lowered[len(heading) :]
        if remainder and not re.match(r"^[\s,;–—-]", remainder):
            continue
        trailing = normalized[len(heading) :].lstrip(" :：,;–—-•·\t")
        return True, trailing

    return False, ""


def _extract_benefits_from_text(text: str) -> List[str]:
    """Extract benefit entries from ``text`` based on common headings."""

    lines = text.splitlines()
    collecting = False
    inline_chunks: List[str] = []
    bullet_items: List[str] = []

    for raw in lines:
        heading, trailing = _match_benefit_heading(raw)
        if heading:
            collecting = True
            inline_chunks = []
            bullet_items = []
            if trailing:
                inline_chunks.append(trailing)
            continue

        if not collecting:
            continue

        line = raw.strip()
        if not line:
            break
        if re.match(r"^[^:]{1,120}:$", line) and not _is_bullet_line(raw):
            break
        if _is_bullet_line(raw):
            cleaned = _clean_bullet(raw)
            if cleaned:
                bullet_items.append(cleaned)
        else:
            inline_chunks.append(line)

    if bullet_items:
        return _normalize_benefit_entries(bullet_items)
    if inline_chunks:
        raw_values: List[str] = []
        for chunk in inline_chunks:
            for part in _BENEFIT_SEP_RE.split(chunk):
                candidate = part.strip()
                if candidate:
                    raw_values.append(candidate)
        return _normalize_benefit_entries(raw_values)
    return []


def _merge_unique(base: List[str], extras: List[str]) -> List[str]:
    """Return ``base`` extended by ``extras`` without duplicates."""

    existing = set(base)
    for item in extras:
        if item not in existing:
            base.append(item)
            existing.add(item)
    return base


def _normalize_skill_marker(value: str) -> str:
    """Return a normalized marker for comparing skill labels."""

    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _dedupe_skill_tiers(requirements: Requirements) -> None:
    """Remove duplicate skills across required/optional buckets."""

    def _dedupe_primary(items: List[str]) -> Tuple[List[str], set[str]]:
        seen: set[str] = set()
        deduped: List[str] = []
        for item in items:
            marker = _normalize_skill_marker(item)
            if not marker or marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        return deduped, seen

    def _dedupe_secondary(items: List[str], primary_markers: set[str]) -> List[str]:
        seen: set[str] = set()
        deduped: List[str] = []
        for item in items:
            marker = _normalize_skill_marker(item)
            if not marker or marker in primary_markers or marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
        return deduped

    hard_req, hard_req_markers = _dedupe_primary(requirements.hard_skills_required)
    soft_req, soft_req_markers = _dedupe_primary(requirements.soft_skills_required)

    requirements.hard_skills_required = hard_req
    requirements.soft_skills_required = soft_req
    requirements.hard_skills_optional = _dedupe_secondary(requirements.hard_skills_optional, hard_req_markers)
    requirements.soft_skills_optional = _dedupe_secondary(requirements.soft_skills_optional, soft_req_markers)


def _parse_salary_value(raw: str) -> Optional[float]:
    """Return a numeric salary value extracted from ``raw``."""

    cleaned = raw.strip().lower().replace(" ", "")
    multiplier = 1.0
    if cleaned.endswith("k"):
        multiplier = 1000.0
        cleaned = cleaned[:-1]
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value * multiplier


def _normalize_percentage(value: float) -> int:
    """Clamp ``value`` to the 0-100 range and round to an integer."""

    return max(0, min(100, int(round(value))))


def _extract_average_days(match: re.Match[str]) -> Optional[float]:
    """Return the average number of days described by ``match``."""

    start = match.group("min")
    end = match.group("max")
    single = match.group("single")
    numbers: List[float] = []
    try:
        if start and end:
            numbers = [float(start), float(end)]
        elif single:
            numbers = [float(single)]
    except ValueError:
        return None
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def _infer_remote_percentage(text: str) -> Optional[int]:
    """Infer remote percentage from textual hints in ``text``."""

    percent_match = _REMOTE_PERCENT_RE.search(text)
    if percent_match:
        try:
            return _normalize_percentage(float(percent_match.group(1)))
        except ValueError:
            return None

    remote_days = _REMOTE_DAYS_REMOTE_RE.search(text)
    if remote_days:
        days = _extract_average_days(remote_days)
        if days is not None:
            return _normalize_percentage(min(days, 5.0) / 5.0 * 100)

    office_days = _REMOTE_DAYS_OFFICE_RE.search(text)
    if office_days:
        days = _extract_average_days(office_days)
        if days is not None:
            return _normalize_percentage((1 - min(days, 5.0) / 5.0) * 100)

    return None


def _is_soft_skill(text: str) -> bool:
    """Return True if ``text`` appears to describe a soft skill."""

    lower = text.lower()
    return any(keyword in lower for keyword in _SOFT_SKILL_KEYWORDS)


def is_soft_skill(text: str) -> bool:
    """Public helper to detect soft skills based on keyword heuristics."""

    return _is_soft_skill(text)


def _contains_optional_hint(text: str) -> bool:
    """Return True if ``text`` includes an optionality marker."""

    lower = text.casefold()
    return any(hint in lower for hint in _OPTIONAL_HINTS)


def _rebalance_optional_skills(requirements: Requirements) -> None:
    """Move skills with optional markers into the *_optional buckets."""

    def _move_optional(source_name: str, target_name: str) -> None:
        source = getattr(requirements, source_name)
        keep: List[str] = []
        for item in source:
            if _contains_optional_hint(item):
                target = getattr(requirements, target_name)
                if item not in target:
                    target.append(item)
            else:
                keep.append(item)
        setattr(requirements, source_name, keep)

    _move_optional("hard_skills_required", "hard_skills_optional")
    _move_optional("soft_skills_required", "soft_skills_optional")


def _language_hits(text: str) -> Set[str]:
    """Return canonical language names referenced in ``text``."""

    lower = text.casefold()
    hits: Set[str] = set()
    for canonical, variants in _LANGUAGE_MAP.items():
        for variant in variants:
            if re.search(rf"\b{re.escape(variant)}\b", lower):
                hits.add(canonical)
                break
    return hits


def _harvest_languages_from_skill_lists(requirements: Requirements) -> None:
    """Move language mentions out of skill lists into language fields."""

    languages_required = normalize_language_list(requirements.languages_required)
    languages_optional = normalize_language_list(requirements.languages_optional)

    def _process(field: str, fallback_optional: bool) -> None:
        source = getattr(requirements, field)
        keep: List[str] = []
        for item in source:
            hits = _language_hits(item)
            if not hits:
                keep.append(item)
                continue
            is_optional = fallback_optional or _contains_optional_hint(item)
            target = languages_optional if is_optional else languages_required
            for language in hits:
                if language not in target:
                    target.append(language)
        setattr(requirements, field, keep)

    _process("hard_skills_required", False)
    _process("soft_skills_required", False)
    _process("hard_skills_optional", True)
    _process("soft_skills_optional", True)

    requirements.languages_required = normalize_language_list(languages_required)
    requirements.languages_optional = normalize_language_list(languages_optional)


def _extract_requirement_bullets(text: str) -> Tuple[List[str], List[str]]:
    """Extract required and optional requirement bullet points from ``text``."""

    lines = text.splitlines()
    required: List[str] = []
    optional: List[str] = []
    mode: Optional[str] = None
    for raw in lines:
        line = raw.strip()
        lower = line.lower().rstrip(":")
        if not line:
            continue
        if lower in _REQ_REQUIRED_HEADINGS:
            mode = "req"
            continue
        if lower in _REQ_OPTIONAL_HEADINGS:
            mode = "opt"
            continue
        if mode and lower in _RESP_HEADINGS:
            mode = None
            continue
        if mode and _is_bullet_line(line):
            cleaned = _clean_bullet(raw)
            if mode == "req":
                required.append(cleaned)
            else:
                optional.append(cleaned)
        elif mode and line.endswith(":") and not _is_bullet_line(line):
            mode = None
        elif (
            mode
            and not _is_bullet_line(line)
            and line
            and not line.endswith(":")
            and (required if mode == "req" else optional)
        ):
            if mode == "req":
                required[-1] += f" {line}"
            else:
                optional[-1] += f" {line}"
    return required, optional


def _split_soft_from_hard(req: NeedAnalysisProfile) -> None:
    """Move soft skills from hard skill lists to soft skill lists."""

    r = req.requirements
    for source_name, target_name in [
        ("hard_skills_required", "soft_skills_required"),
        ("hard_skills_optional", "soft_skills_optional"),
    ]:
        source = getattr(r, source_name)
        keep: List[str] = []
        for item in source:
            if _is_soft_skill(item):
                target = getattr(r, target_name)
                if item not in target:
                    target.append(item)
            else:
                keep.append(item)
        setattr(r, source_name, keep)


def _extract_tools_from_lists(req: NeedAnalysisProfile) -> None:
    """Populate ``tools_and_technologies`` from known tech keywords."""

    techs = set(req.requirements.tools_and_technologies)
    for field in [
        "hard_skills_required",
        "hard_skills_optional",
        "soft_skills_required",
        "soft_skills_optional",
    ]:
        for item in getattr(req.requirements, field):
            techs.update(_find_tech_keywords(item))
    req.requirements.tools_and_technologies = list(techs)


def _extract_languages(text: str) -> Tuple[List[str], List[str]]:
    """Return required and optional languages mentioned in ``text``."""

    req: List[str] = []
    opt: List[str] = []
    lower = text.lower()
    for canon, variants in _LANGUAGE_MAP.items():
        for variant in variants:
            for m in re.finditer(rf"\b{re.escape(variant)}\b", lower):
                window = lower[max(0, m.start() - 20) : m.end() + 20]
                if any(h in window for h in _OPTIONAL_HINTS):
                    if canon not in opt:
                        opt.append(canon)
                else:
                    if canon not in req:
                        req.append(canon)
    return req, opt


def _extract_certifications(text: str) -> List[str]:
    """Extract certification phrases from ``text``."""

    return [m.group(0).strip() for m in _CERT_RE.finditer(text)]


def _find_tech_keywords(text: str) -> Set[str]:
    """Return tech keywords mentioned in ``text`` using known variants."""

    matches: Set[str] = set()
    lower = text.casefold()
    for canonical, variants in _TECH_KEYWORD_VARIANTS.items():
        for variant in variants:
            if re.search(rf"\b{re.escape(variant)}\b", lower):
                matches.add(canonical)
                break
    return matches


def _extract_tech_keywords_from_entries(entries: Sequence[str]) -> Tuple[Set[str], Set[str]]:
    """Return language/framework skills and tools found in ``entries``."""

    skill_hits: Set[str] = set()
    tool_hits: Set[str] = set()
    for entry in entries:
        for match in _find_tech_keywords(entry):
            if match in _TECH_KEYWORDS:
                tool_hits.add(match)
            else:
                skill_hits.add(match)
    return skill_hits, tool_hits


def _harvest_skills_from_responsibilities(
    responsibilities: Sequence[str],
    hard_sink: List[str],
    soft_sink: List[str],
    tool_sink: Set[str],
) -> None:
    """Harvest skill signals embedded inside responsibility sentences."""

    for responsibility in responsibilities:
        skills, tools = _extract_tech_keywords_from_entries([responsibility])
        _merge_unique(hard_sink, sorted(skills))
        tool_sink.update(tools)
        for phrase in _extract_skill_phrases_from_bullet(responsibility):
            _merge_unique(hard_sink, [phrase])
            if _is_soft_skill(phrase):
                _merge_unique(soft_sink, [phrase])


def refine_requirements(profile: NeedAnalysisProfile, text: str) -> NeedAnalysisProfile:
    """Enrich ``profile.requirements`` using heuristics from ``text``."""

    _split_soft_from_hard(profile)
    _extract_tools_from_lists(profile)

    req_bullets, opt_bullets = _extract_requirement_bullets(text)
    hard_req: List[str] = []
    soft_req: List[str] = []
    hard_opt: List[str] = []
    soft_opt: List[str] = []
    tech_tools: Set[str] = set()

    profile.responsibilities.items = list(profile.responsibilities.items or [])

    def _siphon_responsibility_bullets(bullets: List[str], *, optional: bool) -> List[str]:
        cleaned: List[str] = []
        for bullet in bullets:
            responsibility = _clean_bullet(bullet)
            if _looks_like_responsibility_line(responsibility):
                if responsibility:
                    profile.responsibilities.items = _merge_unique(
                        list(profile.responsibilities.items or []), [responsibility]
                    )
                skill_phrases = _extract_skill_phrases_from_bullet(responsibility)
                target_hard = hard_opt if optional else hard_req
                _merge_unique(target_hard, skill_phrases)
                soft_target = soft_opt if optional else soft_req
                _merge_unique(soft_target, [phrase for phrase in skill_phrases if _is_soft_skill(phrase)])
                skills, tools = _extract_tech_keywords_from_entries([responsibility])
                _merge_unique(target_hard, sorted(skills))
                tech_tools.update(tools)
                continue
            cleaned.append(bullet)
        return cleaned

    req_bullets = _siphon_responsibility_bullets(list(req_bullets), optional=False)
    opt_bullets = _siphon_responsibility_bullets(list(opt_bullets), optional=True)

    _harvest_skills_from_responsibilities(profile.responsibilities.items, hard_req, soft_req, tech_tools)
    for item in req_bullets:
        if _is_soft_skill(item):
            soft_req.append(item)
        else:
            hard_req.append(item)
        skills, tools = _extract_tech_keywords_from_entries([item])
        hard_req = _merge_unique(hard_req, sorted(skills))
        tech_tools.update(tools)
    for item in opt_bullets:
        if _is_soft_skill(item):
            soft_opt.append(item)
        else:
            hard_opt.append(item)
        skills, tools = _extract_tech_keywords_from_entries([item])
        hard_opt = _merge_unique(hard_opt, sorted(skills))
        tech_tools.update(tools)

    r = profile.requirements
    r.languages_required = normalize_language_list(r.languages_required)
    r.languages_optional = normalize_language_list(r.languages_optional)
    r.hard_skills_required = _merge_unique(r.hard_skills_required, hard_req)
    r.hard_skills_optional = _merge_unique(r.hard_skills_optional, hard_opt)
    r.soft_skills_required = _merge_unique(r.soft_skills_required, soft_req)
    r.soft_skills_optional = _merge_unique(r.soft_skills_optional, soft_opt)
    r.tools_and_technologies = _merge_unique(r.tools_and_technologies, sorted(tech_tools))

    _rebalance_optional_skills(r)
    _harvest_languages_from_skill_lists(r)
    _dedupe_skill_tiers(r)

    _extract_tools_from_lists(profile)

    langs_req, langs_opt = _extract_languages(text)
    langs_req = normalize_language_list(langs_req)
    langs_opt = normalize_language_list(langs_opt)
    r.languages_required = _merge_unique(r.languages_required, langs_req)
    r.languages_optional = _merge_unique(r.languages_optional, langs_opt)
    r.languages_required = normalize_language_list(r.languages_required)
    r.languages_optional = normalize_language_list(r.languages_optional)

    certs = _extract_certifications(text)
    r.certifications = _merge_unique(r.certifications, certs)
    r.certificates = _merge_unique(r.certificates, certs)
    normalized_payload: NormalizedProfilePayload = normalize_profile(profile)
    return NeedAnalysisProfile.model_validate(normalized_payload)


def extract_responsibilities(text: str) -> List[str]:
    """Extract responsibility bullet points from ``text``.

    The function searches for common responsibility section headings and
    collects subsequent bullet-point lines until the section ends.
    """

    lines = text.splitlines()
    items: List[str] = []
    in_section = False
    for raw_line in lines:
        line = raw_line.strip()
        lower = line.lower().rstrip(":")
        if in_section:
            if not line:
                if items:
                    break
                continue
            if (lower in _RESP_HEADINGS or line.endswith(":")) and not _is_bullet_line(line):
                break
            if _is_bullet_line(line):
                items.append(_clean_bullet(raw_line))
            elif items:
                items[-1] += f" {line}"
        elif lower in _RESP_HEADINGS:
            in_section = True
    return [i for i in items if i]


def _looks_like_responsibility_line(line: str) -> bool:
    """Return ``True`` when ``line`` is action-oriented (duty statement)."""

    cleaned = _clean_bullet(line).strip().lower()
    if not cleaned:
        return False
    if " you will " in cleaned:
        return True
    return any(cleaned.startswith(prefix) for prefix in _RESPONSIBILITY_STARTERS)


def _extract_skill_phrases_from_bullet(entry: str) -> List[str]:
    """Return skill/experience phrases that trail action statements."""

    phrases: List[str] = []
    for match in _SKILL_TAIL_RE.finditer(entry):
        phrase = match.group(1).strip(" -:\t")
        if phrase:
            phrases.append(phrase)
    return phrases


def _line_ends_with_gender_marker(line: str) -> bool:
    return bool(GENDER_SUFFIX_TRAILING_RE.search(line.strip()))


def _should_include_second_line(line: str) -> bool:
    stripped = line.rstrip()
    if not stripped:
        return False
    if _line_ends_with_gender_marker(stripped):
        return True
    return stripped[-1] in {":", "-", "–", "—", "/", "|"}


def _normalize_gender_suffix(title: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        suffix = match.group("suffix").strip()
        return f" {suffix}"

    normalized = GENDER_SUFFIX_INLINE_RE.sub(_replace, title)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized.rstrip("-–—:,/|").strip()


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"[\W_]+", "", value).casefold()


def _segment_is_city(segment: str) -> bool:
    cleaned = segment.strip()
    if not cleaned:
        return False
    lower = cleaned.casefold()
    for city in _COMMON_CITIES:
        if lower == city.casefold():
            return True
    return False


def _is_location_token(token: str, known_locations: set[str]) -> bool:
    normalized = _normalize_for_compare(token)
    if not normalized:
        return False
    if normalized in known_locations:
        return True
    if normalized in _LOCATION_KEYWORD_NORMALIZED:
        return True
    if _segment_is_city(token):
        return True
    return False


def _looks_like_location_line(line: str, known_locations: set[str]) -> bool:
    if not line:
        return False
    stripped = line.strip("-–—•|· ")
    if not stripped:
        return False
    comparable = _normalize_for_compare(stripped)
    if comparable in known_locations:
        return True
    if _segment_is_city(stripped):
        return True
    if _POSTAL_CODE_RE.search(stripped):
        segments = [seg.strip() for seg in re.split(r"[|/•·,]", stripped) if seg.strip()]
        if not segments:
            return True
        if all(_is_location_token(segment, known_locations) or _POSTAL_CODE_RE.search(segment) for segment in segments):
            return True
    segments = [seg.strip() for seg in re.split(r"[|/•·,]", stripped) if seg.strip()]
    if len(segments) > 1:
        if all(
            _is_location_token(segment, known_locations) or _POSTAL_CODE_RE.search(segment) or _segment_is_city(segment)
            for segment in segments
        ):
            return True
    tokens = [tok for tok in stripped.split() if tok]
    if len(tokens) <= 3:
        seen_location = False
        for tok in tokens:
            if _POSTAL_CODE_RE.fullmatch(tok):
                seen_location = True
                continue
            if _is_location_token(tok, known_locations):
                seen_location = True
                continue
            return False
        if seen_location:
            return True
    return False


def _line_matches_known_value(line: str, known_values: set[str]) -> bool:
    if not line:
        return False
    normalized = _normalize_for_compare(line)
    if not normalized:
        return False
    if normalized in known_values:
        return True
    for value in known_values:
        if value and value in normalized:
            return True
    return False


def _should_skip_line(line: str, known_values: set[str], known_locations: set[str]) -> bool:
    if _line_matches_known_value(line, known_values):
        return True
    if _looks_like_location_line(line, known_locations):
        return True
    return False


def _coerce_strings(values) -> list[str]:
    coerced: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidate = value.strip()
        elif value is not None:
            candidate = str(value).strip()
        else:
            continue
        if candidate:
            coerced.append(candidate)
    return coerced


def _collect_locked_values(
    metadata: Mapping[str, object] | None,
    field: str,
    locked_fields: set[str],
) -> list[str]:
    if not isinstance(metadata, Mapping):
        return []
    if field not in locked_fields:
        return []
    hints: list[str] = []
    rules = metadata.get("rules")
    if isinstance(rules, Mapping):
        rule_meta = rules.get(field)
        if isinstance(rule_meta, Mapping):
            value = rule_meta.get("value")
            if value is not None:
                hints.extend(_coerce_strings([value]))
    for key in ("locked_field_values", "locked_fields_map", "locked_hints"):
        mapping = metadata.get(key)
        if isinstance(mapping, Mapping):
            value = mapping.get(field)
            if value is not None:
                hints.extend(_coerce_strings([value]))
    return hints


def guess_job_title(
    text: str,
    *,
    skip_phrases: Sequence[str] | None = None,
    known_locations: Sequence[str] | None = None,
) -> str:
    """Return a basic job title guess from ``text``."""
    if not text:
        return ""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    known_values = {
        _normalize_for_compare(value) for value in skip_phrases or [] if isinstance(value, str) and value.strip()
    }
    location_values = {
        _normalize_for_compare(value) for value in known_locations or [] if isinstance(value, str) and value.strip()
    }
    for index, first_line in enumerate(lines):
        if _should_skip_line(first_line, known_values, location_values):
            continue
        include_second = False
        if index + 1 < len(lines) and _should_include_second_line(first_line):
            second_line = lines[index + 1].lstrip()
            if not _should_skip_line(second_line, known_values, location_values):
                first_line = f"{first_line.rstrip()} {second_line}"
                include_second = True
        candidate = first_line.split("|")[0].strip()
        if not include_second:
            candidate = re.split(r"\s[-–—]\s", candidate)[0].strip()
        title = _normalize_gender_suffix(candidate)
        if not _should_skip_line(title, known_values, location_values):
            return title
    return ""


def guess_company(text: str) -> Tuple[str, str]:
    """Guess company name and optional brand from ``text``."""
    if not text:
        return "", ""
    m = _BRAND_OF_RE.search(text)
    if m:
        brand, company = m.group(1).strip(), m.group(2).strip()
        brand = re.sub(r"^wir sind\s+", "", brand, flags=re.IGNORECASE)
        return company, brand
    m = _COMPANY_FORM_RE.search(text)
    if m:
        return m.group(1).strip(), ""
    m = _WE_ARE_RE.search(text)
    if m:
        name = m.group(1).strip()
        return name, ""
    return "", ""


def guess_company_size(text: str) -> str:
    """Return a normalised employee count extracted from ``text``."""

    if not text:
        return ""
    return extract_company_size(text)


def guess_city(text: str) -> str:
    """Guess primary city from ``text``."""
    if not text:
        return ""
    line_match = _CITY_LINE_RE.search(text)
    if line_match:
        candidate = _clean_city_candidate(line_match.group("city"))
        candidate = normalize_city_name(_trim_city_stopwords(candidate))
        if _city_candidate_is_plausible(candidate):
            return _canonicalize_city_name(candidate)
    address_match = _CITY_ADDRESS_RE.search(text)
    if address_match:
        candidate = _clean_city_candidate(address_match.group("city"))
        candidate = normalize_city_name(_trim_city_stopwords(candidate))
        if _city_candidate_is_plausible(candidate):
            return _canonicalize_city_name(candidate)
    inline_match = CITY_REGEX_IN_PATTERN.search(text)
    if inline_match:
        candidate = _clean_city_candidate(inline_match.group("city"))
        candidate = normalize_city_name(_trim_city_stopwords(candidate))
        if _city_candidate_is_plausible(candidate):
            return _canonicalize_city_name(candidate)
    m = _CITY_HINT_RE.search(text)
    if m:
        candidate = _clean_city_candidate(m.group(1).split("|")[0].split(",")[0])
        candidate = normalize_city_name(_trim_city_stopwords(candidate))
        if _city_candidate_is_plausible(candidate):
            return _canonicalize_city_name(candidate)
    for match in _CITY_IN_RE.finditer(text):
        candidate = _clean_city_candidate(match.group(1))
        candidate = re.split(r"[|,/]", candidate)[0].strip()
        candidate = normalize_city_name(_trim_city_stopwords(candidate))
        if not _city_candidate_is_plausible(candidate):
            continue
        return _canonicalize_city_name(candidate)
    first_line = text.strip().splitlines()[0]
    parts = [p.strip() for p in first_line.split("|")]
    for part in parts:
        for city in _COMMON_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", part):
                return city
    for city in _COMMON_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text):
            return city
    return ""


def _llm_extract_primary_city(text: str) -> str:
    """Use an LLM to recover a plausible city name from ``text``."""

    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    messages = [
        {
            "role": "system",
            "content": (
                "Extract the primary city mentioned in the following job advertisement snippet. "
                "Respond with JSON containing only a 'city' field. Return an empty string when no city is present."
            ),
        },
        {"role": "user", "content": cleaned},
    ]
    response_format = build_json_schema_format(
        name="primary_city_extraction",
        schema=_CITY_FIX_SCHEMA,
        strict=True,
    )
    try:
        result = call_responses_safe(
            messages,
            model=get_model_for(ModelTask.EXTRACTION),
            response_format=response_format,
            temperature=0,
            max_completion_tokens=40,
            reasoning_effort="minimal",
            task=ModelTask.EXTRACTION,
            logger_instance=HEURISTICS_LOGGER,
            context="primary city extraction",
        )
    except Exception:
        return ""

    if result is None:
        HEURISTICS_LOGGER.info("Primary city extraction fell back to heuristics after API failure")
        return ""

    if result.used_chat_fallback:
        HEURISTICS_LOGGER.info("Primary city extraction used classic chat fallback")
    content = (result.content or "").strip()
    if not content:
        return ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return ""
    city_value = payload.get("city")
    if not isinstance(city_value, str):
        return ""
    return normalize_city_name(city_value)


def guess_employment_details(
    text: str,
) -> Tuple[str, str, str, Optional[int]]:
    """Infer employment details from ``text``.

    Returns:
        Tuple of job type, contract type, work policy, and optional remote percentage.
    """

    def _find(mapping: dict[str, list[str]]) -> str:
        for key, kws in mapping.items():
            for kw in kws:
                if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE):
                    return key
        return ""

    job_type = _find(_JOB_TYPE_MAP)
    contract_type = _find(_CONTRACT_TYPE_MAP)
    work_policy = _find(_WORK_POLICY_MAP)

    remote_percentage = _infer_remote_percentage(text)
    if remote_percentage is not None:
        if remote_percentage >= 80:
            inferred_policy = "remote"
        elif remote_percentage <= 20:
            inferred_policy = "onsite"
        else:
            inferred_policy = "hybrid"
        if not work_policy or work_policy != inferred_policy:
            work_policy = inferred_policy

    return job_type, contract_type, work_policy, remote_percentage


def guess_start_date(text: str) -> str:
    """Extract a start date from ``text`` in ISO format if possible."""
    for pattern in _DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(m.group(1), fmt)
                except ValueError:
                    continue
                return dt.strftime("%Y-%m-%d")
    m = _SEASON_RE.search(text)
    if m:
        season = m.group(1).lower()
        year = int(m.group(2))
        month = _SEASON_MONTH.get(season)
        if month:
            return f"{year}-{month:02d}-01"
        return m.group(0)
    m = _IMMEDIATE_RE.search(text)
    if m:
        value = m.group(1).lower()
        if "sofort" in value:
            return "sofort"
        if "immediately" in value:
            return "immediately"
        if (
            "asap" in value
            or "as soon as possible" in value
            or "nächstmöglichen" in value
            or "frühestmöglichen" in value
        ):
            return "asap"
        return value
    return ""


def apply_basic_fallbacks(
    profile: NeedAnalysisProfile,
    text: str,
    *,
    metadata: Mapping[str, object] | None = None,
) -> NeedAnalysisProfile:
    """Fill missing basic fields using heuristics."""

    metadata = metadata if metadata is not None else {}
    autodetect_lang = metadata.get("autodetect_language")
    if not isinstance(autodetect_lang, str):
        autodetect_lang = metadata.get("_autodetect_language")
    language_hint = autodetect_lang if isinstance(autodetect_lang, str) else None

    def _string_set_from_metadata(key: str) -> set[str]:
        value = metadata.get(key, ())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return {item for item in value if isinstance(item, str)}
        return set()

    invalid_fields = _string_set_from_metadata("invalid_fields")
    high_confidence = _string_set_from_metadata("high_confidence_fields")
    locked_fields = _string_set_from_metadata("locked_fields")
    city_field = "location.primary_city"
    country_field = "location.country"
    size_field = "company.size"
    travel_field = "employment.travel_share"
    team_size_field = "position.team_size"
    supervises_field = "position.supervises"
    city_invalid = city_field in invalid_fields
    country_invalid = country_field in invalid_fields

    discarded_city: str | None = None
    invalid_marker = _city_value_is_invalid(profile.location.primary_city)
    if invalid_marker:
        discarded_city = profile.location.primary_city
        profile.location.primary_city = None
        city_invalid = True
        invalid_fields.add(city_field)
        HEURISTICS_LOGGER.info(
            "Discarding invalid location candidate %s (marker: %s)",
            discarded_city,
            invalid_marker,
            extra={
                "heuristic_field": city_field,
                "heuristic_rule": "city_invalid_marker",
                "heuristic_detail": invalid_marker,
            },
        )
        if _city_value_suits_work_schedule(discarded_city):
            existing_schedule = (profile.employment.work_schedule or "").strip()
            schedule_candidates = [existing_schedule, discarded_city]
            merged_schedule: list[str] = []
            for entry in schedule_candidates:
                cleaned = entry.strip()
                if not cleaned:
                    continue
                marker = cleaned.casefold()
                if marker and all(marker != seen.casefold() for seen in merged_schedule):
                    merged_schedule.append(cleaned)
            if merged_schedule:
                profile.employment.work_schedule = ", ".join(merged_schedule)
                _log_heuristic_fill(
                    "employment.work_schedule",
                    "work_schedule_from_location",
                    detail=f"with value {profile.employment.work_schedule!r}",
                )

    def _needs_value(value: Optional[str], field: str) -> bool:
        if field in high_confidence and field not in invalid_fields:
            return False
        if field in invalid_fields:
            return True
        return not (value and value.strip())

    def _is_locked(field: str) -> bool:
        return field in locked_fields

    location_entities = None

    def _mark_field_confidence(field: str, rule: str, *, confidence: float = 0.9) -> None:
        """Record ``field`` as confidently filled via ``rule``."""

        if field not in locked_fields:
            locked_fields.add(field)
        if field not in high_confidence:
            high_confidence.add(field)
        if not isinstance(metadata, MutableMapping):
            return
        metadata["locked_fields"] = sorted(locked_fields)
        metadata["high_confidence_fields"] = sorted(high_confidence)
        sources = metadata.get("field_sources")
        if not isinstance(sources, MutableMapping):
            sources = {}
        else:
            sources = dict(sources)
        sources[field] = {"source": "heuristic", "rule": rule, "confidence": confidence}
        metadata["field_sources"] = dict(sorted(sources.items()))
        confidence_map = metadata.get("field_confidence")
        if not isinstance(confidence_map, MutableMapping):
            confidence_map = {}
        else:
            confidence_map = dict(confidence_map)
        confidence_map[field] = confidence
        metadata["field_confidence"] = dict(sorted(confidence_map.items()))

    if not profile.position.job_title and "position.job_title" not in locked_fields:
        company_hints = _coerce_strings([profile.company.name, profile.company.brand_name])
        company_hints.extend(_collect_locked_values(metadata, "company.name", locked_fields))
        company_hints.extend(_collect_locked_values(metadata, "company.brand_name", locked_fields))
        location_hints = _coerce_strings([profile.location.primary_city, profile.location.country])
        location_hints.extend(_collect_locked_values(metadata, "location.primary_city", locked_fields))
        location_hints.extend(_collect_locked_values(metadata, "location.country", locked_fields))
        skip_phrases = company_hints + _collect_locked_values(metadata, "position.job_title", locked_fields)
        title_guess = guess_job_title(
            text,
            skip_phrases=skip_phrases,
            known_locations=location_hints,
        )
        if title_guess:
            profile.position.job_title = title_guess
            _log_heuristic_fill(
                "position.job_title",
                "job_title_guess",
                detail=f"with value {title_guess!r}",
            )
    if not profile.company.name:
        name, brand = guess_company(text)
        if name:
            profile.company.name = name
            _log_heuristic_fill(
                "company.name",
                "company_name_guess",
                detail=f"with value {name!r}",
            )
        if brand and not profile.company.brand_name:
            profile.company.brand_name = brand
            _log_heuristic_fill(
                "company.brand_name",
                "company_brand_guess",
                detail=f"with value {brand!r}",
            )
    elif not profile.company.brand_name:
        _, brand = guess_company(text)
        if brand:
            profile.company.brand_name = brand
            _log_heuristic_fill(
                "company.brand_name",
                "company_brand_guess",
                detail=f"with value {brand!r}",
            )
    if _needs_value(profile.location.primary_city, city_field):
        # City fallback order: reuse regex-based guess_city first, then fall back to
        # spaCy entity extraction (if available) before retrying the regex when the
        # field is marked invalid. As a last resort, trigger a lightweight LLM call
        # when heuristics cannot provide a plausible city name.
        regex_city_raw = _clean_city_candidate(guess_city(text))
        regex_city = normalize_city_name(_trim_city_stopwords(regex_city_raw))
        city_guess = "" if city_invalid else regex_city
        city_rule = "city_regex" if city_guess else None
        if not city_guess or city_invalid:
            if location_entities is None:
                location_entities = extract_location_entities(text, lang=language_hint)
            if location_entities:
                spa_city_raw = _clean_city_candidate(location_entities.primary_city)
                spa_city = normalize_city_name(_trim_city_stopwords(spa_city_raw))
            else:
                spa_city = ""
            if spa_city:
                city_guess = spa_city
                city_rule = "city_entity"
            elif city_invalid and regex_city:
                city_guess = regex_city
                city_rule = "city_regex_retry"
        candidate_city = normalize_city_name(_trim_city_stopwords(_clean_city_candidate(city_guess)))
        if candidate_city and regex_city and not _city_candidate_is_trustworthy(candidate_city, text, regex_city):
            candidate_city = regex_city
            city_rule = "city_regex_retry" if city_invalid else "city_regex"
        if not candidate_city:
            llm_city = _llm_extract_primary_city(text)
            if llm_city and _city_candidate_is_plausible(llm_city):
                candidate_city = llm_city
                city_rule = "city_llm"
        if candidate_city and _city_candidate_is_plausible(candidate_city):
            canonical_city = _canonicalize_city_name(candidate_city)
            profile.location.primary_city = canonical_city
            _mark_field_confidence(city_field, city_rule or "city_guess")
            _log_heuristic_fill(
                "location.primary_city",
                city_rule or "city_guess",
                detail=f"with value {canonical_city!r}",
            )
            if not profile.company.hq_location:
                profile.company.hq_location = canonical_city
                _mark_field_confidence("company.hq_location", "hq_from_primary_city")
                _log_heuristic_fill(
                    "company.hq_location",
                    "hq_from_primary_city",
                    detail=f"with value {canonical_city!r}",
                )
    if not _is_locked(size_field) and _needs_value(profile.company.size, size_field):
        size_guess = guess_company_size(text)
        if size_guess:
            profile.company.size = size_guess
            _log_heuristic_fill(
                size_field,
                "company_size_regex",
                detail=f"with value {size_guess!r}",
            )
    if _needs_value(profile.location.country, country_field):
        # Country fallback order mirrors the city logic: prefer spaCy geo entities and
        # only fall back to heuristics when no entity is found and the field was invalid.
        if location_entities is None:
            location_entities = extract_location_entities(text, lang=language_hint)
        if location_entities:
            country_guess = location_entities.primary_country or ""
            country_rule = "country_entity" if country_guess else None
        else:
            country_guess = ""
            country_rule = None
        if not country_guess and country_invalid:
            country_guess = ""
        if country_guess:
            profile.location.country = country_guess
            _log_heuristic_fill(
                "location.country",
                country_rule or "country_guess",
                detail=f"with value {country_guess!r}",
            )
    # Employment classification: regex heuristics via guess_employment_details decide
    # job type, contract type, work policy, and remote percentage before any manual
    # overrides.
    job, contract, policy, remote_pct = guess_employment_details(text)
    if not profile.employment.job_type and job:
        profile.employment.job_type = job
        _log_heuristic_fill(
            "employment.job_type",
            "employment_details",
            detail=f"with value {job!r}",
        )
    if not profile.employment.contract_type and contract:
        profile.employment.contract_type = contract
        _log_heuristic_fill(
            "employment.contract_type",
            "employment_details",
            detail=f"with value {contract!r}",
        )
    if not profile.employment.work_policy and policy:
        profile.employment.work_policy = policy
        _log_heuristic_fill(
            "employment.work_policy",
            "employment_details",
            detail=f"with value {policy!r}",
        )
    if remote_pct is not None and profile.employment.remote_percentage is None:
        profile.employment.remote_percentage = remote_pct
        _log_heuristic_fill(
            "employment.remote_percentage",
            "employment_details",
            detail=f"with value {remote_pct!r}",
        )
    if profile.employment.travel_share is None and not _is_locked(travel_field):
        travel_share = _extract_travel_share(text)
        if travel_share is not None:
            profile.employment.travel_share = travel_share
            _mark_field_confidence(travel_field, "travel_share_regex", confidence=0.75)
            _log_heuristic_fill(
                travel_field,
                "travel_share_regex",
                detail=f"with value {travel_share!r}",
            )
    if not profile.meta.target_start_date:
        start = guess_start_date(text)
        if start:
            profile.meta.target_start_date = start
            _log_heuristic_fill(
                "meta.target_start_date",
                "start_date_guess",
                detail=f"with value {start!r}",
            )
    if not profile.responsibilities.items:
        tasks = extract_responsibilities(text)
        if tasks:
            profile.responsibilities.items = tasks
            _log_heuristic_fill(
                "responsibilities.items",
                "responsibilities_section",
                detail=f"with {len(tasks)} entries",
            )
    if not profile.position.role_summary and profile.responsibilities.items:
        profile.position.role_summary = profile.responsibilities.items[0]
        _log_heuristic_fill(
            "position.role_summary",
            "responsibilities_first_item",
            detail="with first responsibility",
        )
    if profile.position.team_size is None and not _is_locked(team_size_field):
        team_size = _extract_team_size(text)
        if team_size is not None:
            profile.position.team_size = team_size
            _mark_field_confidence(team_size_field, "team_size_regex", confidence=0.95)
            _log_heuristic_fill(
                team_size_field,
                "team_size_regex",
                detail=f"with value {team_size!r}",
            )
    if profile.position.supervises is None and not _is_locked(supervises_field):
        direct_reports = _extract_direct_reports(text)
        if direct_reports is not None:
            profile.position.supervises = direct_reports
            _mark_field_confidence(supervises_field, "direct_reports_regex", confidence=0.95)
            _log_heuristic_fill(
                supervises_field,
                "direct_reports_regex",
                detail=f"with value {direct_reports!r}",
            )
    team_field = "position.team_structure"
    if not _is_locked(team_field) and _needs_value(profile.position.team_structure, team_field):
        team_structure = _extract_team_structure(text)
        if team_structure:
            profile.position.team_structure = team_structure
            _log_heuristic_fill(
                team_field,
                "team_structure_phrase",
                detail=f"with value {team_structure!r}",
            )
    reporting_line_field = "position.reporting_line"
    manager_name_field = "position.reporting_manager_name"
    reporting_line_needed = not _is_locked(reporting_line_field) and _needs_value(
        profile.position.reporting_line, reporting_line_field
    )
    manager_name_needed = not _is_locked(manager_name_field) and _needs_value(
        profile.position.reporting_manager_name, manager_name_field
    )
    if reporting_line_needed or manager_name_needed:
        reporting_line, manager_name = _extract_reporting_line(text)
        if reporting_line_needed and reporting_line:
            profile.position.reporting_line = reporting_line
            _log_heuristic_fill(
                reporting_line_field,
                "reporting_line_match",
                detail=f"with value {reporting_line!r}",
            )
        if manager_name_needed and manager_name:
            profile.position.reporting_manager_name = manager_name
            _log_heuristic_fill(
                manager_name_field,
                "reporting_line_match",
                detail=f"with value {manager_name!r}",
            )
    # Contact heuristics: look for labelled HR contact sections and company websites
    # to backfill missing company metadata in the wizard sidebar.
    contact_name_field = "company.contact_name"
    contact_email_field = "company.contact_email"
    contact_phone_field = "company.contact_phone"
    website_field = "company.website"
    existing_contact_email = str(profile.company.contact_email) if profile.company.contact_email else None
    contact_name_needed = not _is_locked(contact_name_field) and _needs_value(
        profile.company.contact_name, contact_name_field
    )
    contact_email_needed = not _is_locked(contact_email_field) and _needs_value(
        existing_contact_email, contact_email_field
    )
    contact_phone_needed = not _is_locked(contact_phone_field) and _needs_value(
        profile.company.contact_phone, contact_phone_field
    )
    email_mismatch = False
    if (
        not _is_locked(contact_email_field)
        and contact_email_field not in high_confidence
        and existing_contact_email
        and profile.company.contact_name
        and not _needs_value(profile.company.contact_name, contact_name_field)
    ):
        email_mismatch = not _email_matches_name(existing_contact_email, profile.company.contact_name)
    footer_details = _extract_footer_contact_details(text)
    if footer_details:
        footer_name = footer_details.get("hr_name") or footer_details.get("manager_name")
        if footer_name and not _is_locked(contact_name_field):
            should_update_name = contact_name_needed or (
                profile.company.contact_name
                and profile.company.contact_name != footer_name
                and contact_name_field not in high_confidence
            )
            if should_update_name:
                profile.company.contact_name = footer_name
                contact_name_needed = False
                _mark_field_confidence(contact_name_field, "footer_contact", confidence=0.95)
                _log_heuristic_fill(
                    contact_name_field,
                    "footer_contact",
                    detail=f"with value {footer_name!r}",
                )
        footer_email = footer_details.get("hr_email")
        if footer_email and not _is_locked(contact_email_field):
            should_update_email = contact_email_needed or (
                existing_contact_email
                and existing_contact_email != footer_email
                and contact_email_field not in high_confidence
            )
            if should_update_email:
                profile.company.contact_email = footer_email
                existing_contact_email = footer_email
                contact_email_needed = False
                _mark_field_confidence(contact_email_field, "footer_contact", confidence=0.95)
                _log_heuristic_fill(
                    contact_email_field,
                    "footer_contact",
                    detail=f"with value {footer_email!r}",
                )
        footer_phone = footer_details.get("phone")
        if footer_phone and not _is_locked(contact_phone_field):
            should_update_phone = contact_phone_needed or (
                profile.company.contact_phone
                and profile.company.contact_phone != footer_phone
                and contact_phone_field not in high_confidence
            )
            if should_update_phone:
                profile.company.contact_phone = footer_phone
                contact_phone_needed = False
                _mark_field_confidence(contact_phone_field, "footer_contact", confidence=0.95)
                _log_heuristic_fill(
                    contact_phone_field,
                    "footer_contact",
                    detail=f"with value {footer_phone!r}",
                )
        footer_website = footer_details.get("website")
        if footer_website and not _is_locked(website_field):
            should_update_website = _needs_value(profile.company.website, website_field) or (
                profile.company.website
                and profile.company.website != footer_website
                and website_field not in high_confidence
            )
            if should_update_website:
                profile.company.website = footer_website
                _mark_field_confidence(website_field, "footer_contact", confidence=0.9)
                _log_heuristic_fill(
                    website_field,
                    "footer_contact",
                    detail=f"with value {footer_website!r}",
                )
        email_mismatch = False
    contact_candidate: _ContactCandidate | None = None
    if contact_name_needed or contact_email_needed or contact_phone_needed or email_mismatch:
        candidates = _extract_contact_candidates(text)
        if candidates:
            contact_candidate = candidates[0]
    if contact_candidate:
        if contact_name_needed and not _is_locked(contact_name_field):
            if profile.company.contact_name != contact_candidate.name:
                profile.company.contact_name = contact_candidate.name
                _mark_field_confidence(contact_name_field, "contact_section")
                _log_heuristic_fill(
                    contact_name_field,
                    "contact_section",
                    detail=f"with value {contact_candidate.name!r}",
                )
        updated_contact_name = profile.company.contact_name or contact_candidate.name
        existing_contact_email = str(profile.company.contact_email) if profile.company.contact_email else None
        email_should_update = False
        if contact_candidate.email and not _is_locked(contact_email_field):
            if contact_email_needed:
                email_should_update = True
            elif (
                updated_contact_name
                and existing_contact_email
                and contact_email_field not in high_confidence
                and not _email_matches_name(existing_contact_email, updated_contact_name)
            ):
                email_should_update = True
        if email_should_update and contact_candidate.email:
            if existing_contact_email != contact_candidate.email:
                profile.company.contact_email = contact_candidate.email
                _mark_field_confidence(contact_email_field, "contact_section")
                _log_heuristic_fill(
                    contact_email_field,
                    "contact_section",
                    detail=f"with value {contact_candidate.email!r}",
                )
        if contact_candidate.phone and not _is_locked(contact_phone_field):
            if contact_phone_needed or (
                not profile.company.contact_phone and contact_phone_field not in high_confidence
            ):
                if profile.company.contact_phone != contact_candidate.phone:
                    profile.company.contact_phone = contact_candidate.phone
                    _mark_field_confidence(contact_phone_field, "contact_section")
                    _log_heuristic_fill(
                        contact_phone_field,
                        "contact_section",
                        detail=f"with value {contact_candidate.phone!r}",
                    )
    contact_email_needed = not _is_locked(contact_email_field) and _needs_value(
        profile.company.contact_email, contact_email_field
    )
    contact_phone_needed = not _is_locked(contact_phone_field) and _needs_value(
        profile.company.contact_phone, contact_phone_field
    )
    if contact_email_needed or contact_phone_needed:
        generic_email, generic_phone = _extract_generic_contact_details(text)
        if contact_email_needed and generic_email:
            profile.company.contact_email = generic_email
            _mark_field_confidence(contact_email_field, "generic_contact", confidence=0.6)
            _log_heuristic_fill(
                contact_email_field,
                "generic_contact",
                detail=f"with value {generic_email!r}",
            )
        if contact_phone_needed and generic_phone:
            profile.company.contact_phone = generic_phone
            _mark_field_confidence(contact_phone_field, "generic_contact", confidence=0.6)
            _log_heuristic_fill(
                contact_phone_field,
                "generic_contact",
                detail=f"with value {generic_phone!r}",
            )
    if not _is_locked(website_field) and _needs_value(profile.company.website, website_field):
        website = _extract_company_website(text)
        if website:
            profile.company.website = website
            _mark_field_confidence(website_field, "company_website_regex")
            _log_heuristic_fill(
                website_field,
                "company_website_regex",
                detail=f"with value {website!r}",
            )
    # Compensation heuristics: attempt range detection first, then single-value
    # mentions, and finally flag variable pay + bonus percentage if keywords appear.
    compensation = profile.compensation
    if not (compensation.salary_min and compensation.salary_max):
        range_match = _SALARY_RANGE_RE.search(text)
        if range_match:
            minimum = _parse_salary_value(range_match.group(1))
            maximum = _parse_salary_value(range_match.group(2))
            if minimum is not None and maximum is not None:
                compensation.salary_min = minimum
                compensation.salary_max = maximum
                if not compensation.currency:
                    compensation.currency = "EUR"
                compensation.salary_provided = True
                _log_heuristic_fill(
                    "compensation.salary_min",
                    "salary_range_regex",
                    detail=f"with value {minimum!r}",
                )
                _log_heuristic_fill(
                    "compensation.salary_max",
                    "salary_range_regex",
                    detail=f"with value {maximum!r}",
                )
    if not (compensation.salary_min and compensation.salary_max):
        single_match = _SALARY_SINGLE_RE.search(text)
        if single_match:
            raw = single_match.group(1) or single_match.group(2)
            if raw:
                value = _parse_salary_value(raw)
                if value is not None:
                    compensation.salary_min = value
                    compensation.salary_max = value
                    if not compensation.currency:
                        compensation.currency = "EUR"
                    compensation.salary_provided = True
                    _log_heuristic_fill(
                        "compensation.salary_min",
                        "salary_single_regex",
                        detail=f"with value {value!r}",
                    )
                    _log_heuristic_fill(
                        "compensation.salary_max",
                        "salary_single_regex",
                        detail=f"with value {value!r}",
                    )
    if not compensation.variable_pay:
        if re.search(r"variable|bonus|provision|prämie|commission", text, re.IGNORECASE):
            compensation.variable_pay = True
            _log_heuristic_fill(
                "compensation.variable_pay",
                "variable_pay_keywords",
                detail="detected compensation keywords",
            )
        pct = _BONUS_PERCENT_RE.search(text)
        if pct:
            compensation.bonus_percentage = float(pct.group(1))
            compensation.variable_pay = True
            _log_heuristic_fill(
                "compensation.bonus_percentage",
                "bonus_percentage_regex",
                detail=f"with value {float(pct.group(1))!r}",
            )
        if compensation.variable_pay and not compensation.commission_structure:
            btxt = _BONUS_TEXT_RE.search(text)
            if btxt:
                compensation.commission_structure = btxt.group(0).strip()
                _log_heuristic_fill(
                    "compensation.commission_structure",
                    "commission_structure_regex",
                    detail="captured incentive description",
                )
    benefits = _extract_benefits_from_text(text)
    if benefits:
        existing_benefits = list(compensation.benefits or [])
        merged_benefits = _normalize_benefit_entries(existing_benefits + benefits)
        if merged_benefits:
            compensation.benefits = merged_benefits
            _mark_field_confidence("compensation.benefits", "benefits_section")
            _log_heuristic_fill(
                "compensation.benefits",
                "benefits_section",
                detail=f"with {len(merged_benefits)} entries",
            )
    company_benefits = _extract_benefits_from_lexicon(text)
    if company_benefits:
        existing_company_benefits = list(profile.company.benefits or [])
        merged_company_benefits = _normalize_benefit_entries(existing_company_benefits + company_benefits)
        if merged_company_benefits:
            profile.company.benefits = merged_company_benefits
            _mark_field_confidence("company.benefits", "benefit_lexicon")
            _log_heuristic_fill(
                "company.benefits",
                "benefit_lexicon",
                detail=f"with {len(merged_company_benefits)} entries",
            )
    country = normalize_country(profile.location.country)
    profile.location.country = country
    return refine_requirements(profile, text)
