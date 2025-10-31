"""Shared spaCy helpers for location entity extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Iterable, List

try:  # pragma: no cover - optional dependency guard
    import spacy
except ImportError:  # pragma: no cover - fallback when dependency missing
    spacy = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from spacy.language import Language
else:  # pragma: no cover - only used when spaCy is missing at runtime
    Language = Any  # type: ignore[assignment,misc]

try:  # pragma: no cover - optional dependency guard
    import pycountry
except ImportError:  # pragma: no cover - fallback when dependency missing
    pycountry = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


_MODEL_NAME = "de_core_news_sm"
_OPTIONAL_MODELS: tuple[str, ...] = ("en_core_web_sm", "xx_ent_wiki_sm")
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
def _load_de_pipeline() -> Language:
    """Return the German spaCy pipeline or raise if unavailable."""

    if spacy is None:
        raise RuntimeError(
            "spaCy is not installed. Install the optional NLP dependencies to enable location entity extraction."
        )
    try:
        return spacy.load(_MODEL_NAME)
    except OSError as exc:  # pragma: no cover - import error surface area
        raise RuntimeError(
            "spaCy model 'de_core_news_sm' is not installed. "
            "Install the optional extras via 'pip install .[ingest]' to enable location extraction."
        ) from exc


@lru_cache(maxsize=None)
def _load_optional_pipeline(model_name: str) -> Language | None:
    """Best-effort loader for non-German spaCy pipelines."""

    if spacy is None:
        return None
    try:
        return spacy.load(model_name)
    except OSError:  # pragma: no cover - optional dependency guard
        return None


def _iter_model_candidates(lang_key: str) -> Iterable[str]:
    """Yield spaCy model names to try for a given language key."""

    if not lang_key or lang_key.startswith("de"):
        yield _MODEL_NAME
        return

    # Prefer the English pipeline whenever English has been detected.
    ordered_optional = _OPTIONAL_MODELS
    if not lang_key.startswith("en"):
        # For non-English languages we still attempt multilingual first to
        # maximise the chance of a match while keeping English as a fallback.
        ordered_optional = ("xx_ent_wiki_sm", "en_core_web_sm")

    for model_name in ordered_optional:
        yield model_name

    # Fall back to German as a final attempt to preserve previous behaviour.
    yield _MODEL_NAME


def _normalise_lang_key(lang: str | None) -> str:
    if not lang:
        return ""
    return lang.split("-", 1)[0].casefold()


def get_shared_pipeline(lang: str | None = None) -> Language | None:
    """Load a spaCy pipeline suitable for ``lang``."""

    if spacy is None:
        logger.debug(
            "spaCy not installed – location entity extraction disabled.",
        )
        return None

    lang_key = _normalise_lang_key(lang)
    for model_name in _iter_model_candidates(lang_key):
        if model_name == _MODEL_NAME:
            try:
                return _load_de_pipeline()
            except RuntimeError:
                continue
        pipeline = _load_optional_pipeline(model_name)
        if pipeline is not None:
            return pipeline
    return None


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


def extract_location_entities(text: str, lang: str | None = None) -> LocationEntities:
    """Extract potential city/country entities from ``text`` using spaCy."""

    if not text.strip():
        return LocationEntities([], [])

    pipeline = get_shared_pipeline(lang)
    if pipeline is None:
        return LocationEntities([], [])

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
