"""Rule-based extraction helpers for structured content blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Sequence, cast

from nlp.entities import LocationEntities, _is_country, extract_location_entities

from ingest.types import ContentBlock

EMAIL_FIELD = "company.contact_email"
SALARY_MIN_FIELD = "compensation.salary_min"
SALARY_MAX_FIELD = "compensation.salary_max"
SALARY_PROVIDED_FIELD = "compensation.salary_provided"
CURRENCY_FIELD = "compensation.currency"
CITY_FIELD = "location.primary_city"
COUNTRY_FIELD = "location.country"
INDUSTRY_FIELD = "company.industry"


@dataclass(slots=True)
class RuleMatch:
    """Container describing a single rule-based match."""

    field: str
    value: Any
    confidence: float
    source_text: str
    rule: str
    block_index: int | None = None
    block_type: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return metadata for persisting the match alongside profile data."""

        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_text": self.source_text,
            "rule": self.rule,
            "block_index": self.block_index,
            "block_type": self.block_type,
            "locked": True,
        }


RuleMatchMap = Mapping[str, RuleMatch]

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SALARY_RE = re.compile(
    r"(?P<prefix>(?:salary|gehalt|compensation|vergütung|pay)[^\d]{0,12})?"
    r"(?P<currency>[$€£]|usd|eur|chf|gbp|euro)?\s*"
    r"(?P<min>\d[\d.,]*(?:k)?)"
    r"(?:\s*(?:[-–]|to)\s*(?P<currency_mid>[$€£]|usd|eur|chf|gbp|euro)?\s*(?P<max>\d[\d.,]*(?:k)?))?"
    r"\s*(?P<currency_after>[$€£]|usd|eur|chf|gbp|euro)?",
    re.IGNORECASE,
)
_LOCATION_LINE_RE = re.compile(
    r"(?:^|\b)(?P<prefix>location|standort|ort|arbeitsort|einsatzort|based in|land|country|city)"
    r"[:\-\s]+(?P<value>[A-ZÄÖÜa-zäöüß0-9 ,./@-]+)",
    re.IGNORECASE,
)
_INDUSTRY_LINE_RE = re.compile(
    r"(?:^|\b)(?P<prefix>branche|industry)[:\-\s]+(?P<value>[A-ZÄÖÜa-zäöüß0-9 ,./&-]+)",
    re.IGNORECASE,
)
_CITY_COUNTRY_RE = re.compile(
    r"\b([A-ZÄÖÜ][\wÄÖÜäöüß'\-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß'\-]+)*)\s*,\s*([A-ZÄÖÜ][\wÄÖÜäöüß'\-]+)\b"
)

_KNOWN_CITY_NAMES = {
    "berlin",
    "düsseldorf",
    "duesseldorf",
    "munich",
    "münchen",
    "muenchen",
    "hamburg",
    "stuttgart",
    "frankfurt",
    "cologne",
    "köln",
    "koeln",
    "leipzig",
    "bonn",
    "essen",
    "dortmund",
    "dresden",
    "nuremberg",
    "nürnberg",
    "nuernberg",
    "hannover",
    "bremen",
    "mannheim",
    "karlsruhe",
    "münster",
    "muenster",
    "aachen",
    "augsburg",
    "braunschweig",
    "chemnitz",
    "erfurt",
    "freiburg",
    "heilbronn",
    "kassel",
    "kiel",
    "ludwigshafen",
    "magdeburg",
    "potsdam",
    "rostock",
    "saarbrücken",
    "saarbruecken",
    "ulm",
    "wiesbaden",
    "würzburg",
    "wuerzburg",
    "zurich",
    "zürich",
    "zuerich",
    "vienna",
    "wien",
    "basel",
    "bern",
    "geneva",
    "genf",
}

_DISQUALIFIED_CITY_TOKENS = {
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "office",
    "home office",
    "home-office",
    "weltweit",
    "worldwide",
    "flexibel",
    "flexible",
    "n/a",
    "keine",
    "k.a.",
}

_TABLE_KEYWORDS = {
    "email": EMAIL_FIELD,
    "e-mail": EMAIL_FIELD,
    "mail": EMAIL_FIELD,
    "contact email": EMAIL_FIELD,
    "gehalt": SALARY_MIN_FIELD,
    "salary": SALARY_MIN_FIELD,
    "vergütung": SALARY_MIN_FIELD,
    "compensation": SALARY_MIN_FIELD,
    "einsatzort": CITY_FIELD,
    "standort": CITY_FIELD,
    "location": CITY_FIELD,
    "city": CITY_FIELD,
    "ort": CITY_FIELD,
    "branche": INDUSTRY_FIELD,
    "land": COUNTRY_FIELD,
    "country": COUNTRY_FIELD,
}

_RULE_PRIORITIES = {
    "regex.email": 400,
    "regex.salary": 350,
    "regex.location": 300,
    "regex.industry": 250,
    "layout.table": 100,
}


def apply_rules(blocks: Sequence[ContentBlock]) -> dict[str, RuleMatch]:
    """Run regex and layout heuristics over ``blocks`` and return matches."""

    matches: dict[str, RuleMatch] = {}
    for index, block in enumerate(blocks):
        for match in _iter_block_matches(block, index):
            current = matches.get(match.field)
            if current is None:
                matches[match.field] = match
                continue
            if _is_better_match(match, current):
                matches[match.field] = match
    return matches


def matches_to_patch(matches: RuleMatchMap) -> dict[str, Any]:
    """Convert ``matches`` to a nested dict suitable for profile merging."""

    patch: dict[str, Any] = {}
    for match in matches.values():
        _set_path(patch, match.field, match.value)
    return patch


def build_rule_metadata(matches: RuleMatchMap) -> dict[str, Any]:
    """Build a metadata payload containing confidence and locking info."""

    rules_meta = {field: match.to_metadata() for field, match in matches.items()}
    locked = sorted(rules_meta.keys())
    return {
        "rules": rules_meta,
        "locked_fields": locked,
        "high_confidence_fields": locked,
    }


def _iter_block_matches(block: ContentBlock, index: int) -> Iterable[RuleMatch]:
    text = block.text or ""
    if not text.strip():
        return []

    results: list[RuleMatch] = []
    layout_matches: list[RuleMatch] = []
    if block.type == "table":
        # For tables we apply layout-aware parsing first, then fall back to regex.
        layout_matches = list(_table_matches(block, index))
        results.extend(layout_matches)
    layout_fields = {match.field for match in layout_matches}
    for regex_match in _regex_email_matches(text, index, block):
        if regex_match.field not in layout_fields:
            results.append(regex_match)
    for regex_match in _regex_salary_matches(text, index, block):
        if regex_match.field not in layout_fields:
            results.append(regex_match)
    for regex_match in _regex_location_matches(text, index, block):
        if regex_match.field not in layout_fields:
            results.append(regex_match)
    for regex_match in _regex_industry_matches(text, index, block):
        if regex_match.field not in layout_fields:
            results.append(regex_match)
    return results


def _regex_email_matches(
    text: str, index: int, block: ContentBlock
) -> Iterable[RuleMatch]:
    match = _EMAIL_RE.search(text)
    if not match:
        return []
    email = match.group(0).lower()
    return [
        RuleMatch(
            field=EMAIL_FIELD,
            value=email,
            confidence=0.99,
            source_text=match.group(0),
            rule="regex.email",
            block_index=index,
            block_type=block.type,
        )
    ]


def _regex_salary_matches(
    text: str, index: int, block: ContentBlock
) -> Iterable[RuleMatch]:
    match = _SALARY_RE.search(text)
    if not match:
        return []
    if not (
        match.group("currency")
        or match.group("currency_mid")
        or match.group("currency_after")
        or match.group("prefix")
    ):
        return []
    span = match.group(0)
    currency = _normalize_currency(
        match.group("currency")
        or match.group("currency_mid")
        or match.group("currency_after")
    )
    minimum = _normalize_salary_value(match.group("min"))
    maximum = (
        _normalize_salary_value(match.group("max")) if match.group("max") else None
    )
    if maximum is None:
        maximum = minimum
    results: list[RuleMatch] = []
    if minimum is not None:
        results.append(
            RuleMatch(
                field=SALARY_MIN_FIELD,
                value=minimum,
                confidence=0.9,
                source_text=span,
                rule="regex.salary",
                block_index=index,
                block_type=block.type,
            )
        )
    if maximum is not None:
        results.append(
            RuleMatch(
                field=SALARY_MAX_FIELD,
                value=maximum,
                confidence=0.9,
                source_text=span,
                rule="regex.salary",
                block_index=index,
                block_type=block.type,
            )
        )
    if currency:
        results.append(
            RuleMatch(
                field=CURRENCY_FIELD,
                value=currency,
                confidence=0.9,
                source_text=span,
                rule="regex.salary",
                block_index=index,
                block_type=block.type,
            )
        )
    if results:
        results.append(
            RuleMatch(
                field=SALARY_PROVIDED_FIELD,
                value=True,
                confidence=0.9,
                source_text=span,
                rule="regex.salary",
                block_index=index,
                block_type=block.type,
            )
        )
    return results


def _regex_location_matches(
    text: str, index: int, block: ContentBlock
) -> Iterable[RuleMatch]:
    city, country = _extract_location(text)
    if not city and not country:
        return []
    span_match = _LOCATION_LINE_RE.search(text) or _CITY_COUNTRY_RE.search(text)
    source = span_match.group(0) if span_match else text.strip()[:120]
    confidence = 0.85 if span_match else 0.6
    results: list[RuleMatch] = []
    if city:
        results.append(
            RuleMatch(
                field=CITY_FIELD,
                value=city,
                confidence=confidence,
                source_text=source,
                rule="regex.location",
                block_index=index,
                block_type=block.type,
            )
        )
    if country:
        results.append(
            RuleMatch(
                field=COUNTRY_FIELD,
                value=country,
                confidence=confidence,
                source_text=source,
                rule="regex.location",
                block_index=index,
                block_type=block.type,
            )
        )
    return results


def _regex_industry_matches(
    text: str, index: int, block: ContentBlock
) -> Iterable[RuleMatch]:
    match = _INDUSTRY_LINE_RE.search(text)
    if not match:
        return []
    value = match.group("value").strip()
    if not value:
        return []
    lower_value = value.lower()
    if "http" in lower_value or "@" in value:
        return []
    return [
        RuleMatch(
            field=INDUSTRY_FIELD,
            value=value,
            confidence=0.75,
            source_text=match.group(0),
            rule="regex.industry",
            block_index=index,
            block_type=block.type,
        )
    ]


def _table_matches(block: ContentBlock, index: int) -> Iterable[RuleMatch]:
    rows = (block.metadata or {}).get("rows") if block.metadata else None
    if not rows:
        return []
    matches: list[RuleMatch] = []
    for row in rows:
        if not isinstance(row, Sequence) or len(row) < 2:
            continue
        header, value = row[0].strip(), row[1].strip()
        if not header or not value:
            continue
        key = header.lower()
        field = _TABLE_KEYWORDS.get(key)
        if not field:
            continue
        if field == EMAIL_FIELD:
            email_match = _EMAIL_RE.search(value)
            if not email_match:
                continue
            matches.append(
                RuleMatch(
                    field=EMAIL_FIELD,
                    value=email_match.group(0).lower(),
                    confidence=0.92,
                    source_text=f"{header}: {value}",
                    rule="layout.table",
                    block_index=index,
                    block_type=block.type,
                )
            )
            continue
        if field == CITY_FIELD:
            city, country = _extract_location(value)
            if not city:
                candidate = value.split(",")[0].strip()
                entities = _safe_location_entities(value)
                if _is_valid_city_candidate(candidate, entities=entities):
                    city = candidate
            if city:
                matches.append(
                    RuleMatch(
                        field=CITY_FIELD,
                        value=city,
                        confidence=0.82,
                        source_text=f"{header}: {value}",
                        rule="layout.table",
                        block_index=index,
                        block_type=block.type,
                    )
                )
            if country:
                matches.append(
                    RuleMatch(
                        field=COUNTRY_FIELD,
                        value=country,
                        confidence=0.82,
                        source_text=f"{header}: {value}",
                        rule="layout.table",
                        block_index=index,
                        block_type=block.type,
                    )
                )
            continue
        if field == COUNTRY_FIELD:
            city, country = _extract_location(value, prefix_hint=key)
            if city:
                matches.append(
                    RuleMatch(
                        field=CITY_FIELD,
                        value=city,
                        confidence=0.82,
                        source_text=f"{header}: {value}",
                        rule="layout.table",
                        block_index=index,
                        block_type=block.type,
                    )
                )
            if not country and not city:
                fallback = value.split(",")[-1].strip()
                country = fallback or None
            if country:
                matches.append(
                    RuleMatch(
                        field=COUNTRY_FIELD,
                        value=country,
                        confidence=0.82,
                        source_text=f"{header}: {value}",
                        rule="layout.table",
                        block_index=index,
                        block_type=block.type,
                    )
                )
            continue
        if field == SALARY_MIN_FIELD:
            salary_matches = list(_regex_salary_matches(value, index, block))
            for item in salary_matches:
                matches.append(
                    RuleMatch(
                        field=item.field,
                        value=item.value,
                        confidence=min(item.confidence, 0.88),
                        source_text=f"{header}: {value}",
                        rule="layout.table",
                        block_index=index,
                        block_type=block.type,
                    )
                )
            continue
        matches.append(
            RuleMatch(
                field=field,
                value=value,
                confidence=0.75,
                source_text=f"{header}: {value}",
                rule="layout.table",
                block_index=index,
                block_type=block.type,
            )
        )
    return matches


def _extract_location(text: str, prefix_hint: str | None = None) -> tuple[str | None, str | None]:
    text = text.strip()
    if not text:
        return None, None
    line_match = _LOCATION_LINE_RE.search(text)
    hint = (prefix_hint or "").strip().strip(":").lower()
    prefix = hint or ((line_match.group("prefix") or "").lower() if line_match else "")
    if line_match:
        raw = line_match.group("value").strip()
    else:
        pair_match = _CITY_COUNTRY_RE.search(text)
        raw = pair_match.group(0).strip() if pair_match else text
    if not raw:
        return None, None

    raw_lower = raw.lower()
    if any(char.isdigit() for char in raw) or "http" in raw_lower or "@" in raw:
        return None, None
    entities = _safe_location_entities(text)
    # Prefer comma separated "City, Country" structures.
    if "," in raw:
        city_part, _, country_part = raw.partition(",")
        city = city_part.strip() or None
        country = country_part.strip() or None
        if city and not _is_valid_city_candidate(city, entities=entities):
            city = None
        if country and not _is_valid_country_candidate(country, entities=entities):
            country = None
        if prefix in {"land", "country"}:
            if country:
                return city, country
            if city:
                if _is_country(city):
                    return None, city
                if _is_valid_city_candidate(city, entities=entities):
                    return city, None
        return city, country
    tokens = [token.strip() for token in re.split(r"\s+-\s+|/", raw) if token.strip()]
    if len(tokens) >= 2:
        city_token = tokens[0]
        country_token = tokens[-1]
        city = city_token or None
        if city and not _is_valid_city_candidate(city, entities=entities):
            city = None
        country = country_token or None
        if country and not _is_valid_country_candidate(country, entities=entities):
            country = None
        return city, country
    if prefix in {"land", "country"}:
        cleaned = raw.strip()
        if not cleaned:
            return None, None
        if _is_country(cleaned):
            return None, cleaned
        if _is_valid_city_candidate(cleaned, entities=entities):
            return cleaned, None
        return None, cleaned
    cleaned = raw.strip() or None
    if not cleaned:
        return None, None
    if not _is_valid_city_candidate(cleaned, entities=entities):
        return None, None
    return cleaned, None


def _safe_location_entities(text: str) -> LocationEntities | None:
    try:
        return extract_location_entities(text)
    except Exception:  # pragma: no cover - defensive guard around optional model
        return None


def _is_valid_city_candidate(
    candidate: str, *, entities: LocationEntities | None
) -> bool:
    candidate = candidate.strip()
    if not candidate:
        return False
    if not any(char.isalpha() for char in candidate):
        return False
    lower_candidate = candidate.casefold()
    if lower_candidate in _DISQUALIFIED_CITY_TOKENS:
        return False
    if entities is not None:
        city_matches = {city.casefold() for city in entities.cities}
        if lower_candidate in city_matches:
            return True
        country_matches = {country.casefold() for country in entities.countries}
        if lower_candidate in country_matches:
            return False
    if lower_candidate in _KNOWN_CITY_NAMES:
        return True
    # Basic structural heuristics when spaCy is unavailable.
    parts = [part for part in re.split(r"[-\s]+", candidate) if part]
    if len(parts) >= 2 and all(part[0].isalpha() and part[0].isupper() for part in parts):
        combined = " ".join(parts).casefold()
        if combined not in _DISQUALIFIED_CITY_TOKENS:
            return True
    if entities is None and candidate and candidate[0].isupper() and len(candidate) >= 3:
        return True
    return False


def _is_valid_country_candidate(
    candidate: str, *, entities: LocationEntities | None
) -> bool:
    candidate = candidate.strip()
    if not candidate:
        return False
    if not any(char.isalpha() for char in candidate):
        return False
    lower_candidate = candidate.casefold()
    if entities is None:
        return True
    country_matches = {country.casefold() for country in entities.countries}
    if lower_candidate in country_matches:
        return True
    city_matches = {city.casefold() for city in entities.cities}
    return lower_candidate not in city_matches


def _normalize_salary_value(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.strip().lower().replace(" ", "")
    multiplier = 1.0
    if cleaned.endswith("k"):
        multiplier = 1000.0
        cleaned = cleaned[:-1]
    cleaned = cleaned.replace(".", "").replace(",", "")
    if not cleaned or not re.match(r"^\d+(?:\.\d+)?$", cleaned):
        return None
    try:
        return float(cleaned) * multiplier
    except ValueError:  # pragma: no cover - defensive
        return None


def _normalize_currency(token: str | None) -> str | None:
    if not token:
        return None
    normalized = token.strip().upper().replace(".", "")
    mapping = {
        "€": "EUR",
        "EUR": "EUR",
        "EURO": "EUR",
        "$": "USD",
        "USD": "USD",
        "£": "GBP",
        "GBP": "GBP",
        "CHF": "CHF",
    }
    return mapping.get(normalized)


def _set_path(target: MutableMapping[str, Any], path: str, value: Any) -> None:
    cursor: MutableMapping[str, Any] = target
    parts = path.split(".")
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, MutableMapping):
            child = {}
            cursor[part] = child
        cursor = cast(MutableMapping[str, Any], child)
    cursor[parts[-1]] = value


def _is_better_match(candidate: RuleMatch, current: RuleMatch) -> bool:
    candidate_priority = _RULE_PRIORITIES.get(candidate.rule, 0)
    current_priority = _RULE_PRIORITIES.get(current.rule, 0)
    if candidate_priority != current_priority:
        return candidate_priority > current_priority
    return candidate.confidence >= current.confidence


__all__ = [
    "RuleMatch",
    "apply_rules",
    "matches_to_patch",
    "build_rule_metadata",
]
