"""Shared spaCy helpers for location entity extraction."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List

import spacy
from spacy.language import Language

try:  # pragma: no cover - optional dependency guard
    import pycountry
except ImportError:  # pragma: no cover - fallback when dependency missing
    pycountry = None  # type: ignore[assignment]


_MODEL_NAME = "de_core_news_sm"
_LOCATION_LABELS = {"GPE", "LOC"}
_COUNTRY_ALIASES = {
    "deutschland",
    "bundesrepublik deutschland",
    "germany",
    "österreich",
    "austria",
    "schweiz",
    "switzerland",
}

_LOCATION_PREFIXES = {
    "arbeitsort",
    "standort",
    "einsatzort",
    "ort",
    "city",
    "location",
    "land",
    "country",
}

if pycountry is not None:  # pragma: no branch - executed when dependency available
    _COUNTRY_CODES = {country.alpha_2 for country in pycountry.countries}
    _COUNTRY_CODES.update(country.alpha_3 for country in pycountry.countries)
else:  # pragma: no cover - exercised only when dependency missing
    _COUNTRY_CODES = {"DE", "DEU", "AT", "AUT", "CH", "CHE"}


@lru_cache(maxsize=1)
def get_shared_pipeline() -> Language:
    """Load and cache the shared spaCy pipeline."""

    try:
        return spacy.load(_MODEL_NAME)
    except OSError as exc:  # pragma: no cover - import error surface area
        raise RuntimeError(
            "spaCy model 'de_core_news_sm' is not installed. "
            "Install dependencies via requirements.txt to enable location extraction."
        ) from exc


def _normalise_token(value: str) -> str:
    value = value.strip().strip(",;:\u2026")
    value = _strip_location_prefix(value)
    if not value:
        return ""
    if value.isupper():
        return value
    if value.islower():
        # Preserve abbreviations while still capitalising common nouns.
        if len(value) <= 3:
            return value.upper()
        return value.title()
    return value


def _strip_location_prefix(value: str) -> str:
    tokens = value.split()
    while tokens:
        head = tokens[0].casefold().rstrip(":")
        if head in _LOCATION_PREFIXES:
            tokens.pop(0)
            continue
        break
    return " ".join(tokens)


def _is_country(value: str) -> bool:
    if not value:
        return False
    lower = value.casefold()
    if lower in _COUNTRY_ALIASES:
        return True
    if lower in _COUNTRY_CODES:
        return True
    if pycountry is None:
        return False
    try:
        pycountry.countries.lookup(value)
    except LookupError:
        return False
    return True


def _append_unique(items: List[str], seen: set[str], value: str) -> None:
    key = value.casefold()
    if key not in seen:
        items.append(value)
        seen.add(key)


@dataclass(slots=True)
class LocationEntities:
    """Container for extracted city and country candidates."""

    cities: List[str]
    countries: List[str]

    @property
    def primary_city(self) -> str | None:
        return self.cities[0] if self.cities else None

    @property
    def primary_country(self) -> str | None:
        return self.countries[0] if self.countries else None


def extract_location_entities(text: str) -> LocationEntities:
    """Extract potential city/country entities from ``text`` using spaCy."""

    if not text.strip():
        return LocationEntities([], [])

    pipeline = get_shared_pipeline()
    doc = pipeline(text)
    cities: List[str] = []
    countries: List[str] = []
    seen_cities: set[str] = set()
    seen_countries: set[str] = set()

    for entity in doc.ents:
        if entity.label_ not in _LOCATION_LABELS:
            continue
        candidate = _normalise_token(entity.text)
        if not candidate:
            continue
        if _is_country(candidate):
            _append_unique(countries, seen_countries, candidate)
        else:
            _append_unique(cities, seen_cities, candidate)

    return LocationEntities(cities=cities, countries=countries)

