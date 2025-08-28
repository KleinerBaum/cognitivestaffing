import re
from typing import Tuple

from models.need_analysis import NeedAnalysisProfile

_GENDER_RE = re.compile(
    r"\s*\((?:[mwfd]\s*/){2}[mwfd]|all genders\)\s*",
    re.IGNORECASE,
)
_BRAND_OF_RE = re.compile(
    r"([A-ZÄÖÜ][\w& ]+),\s+ein[^,]*?\s+der\s+([A-ZÄÖÜ][\w& ]+(?:GmbH|AG|Inc|Ltd|UG|KG))",
    re.IGNORECASE,
)
_COMPANY_FORM_RE = re.compile(
    r"\b([A-ZÄÖÜ][\w& ]+(?:GmbH|AG|Inc|Ltd|UG|KG))\b",
)
_WE_ARE_RE = re.compile(r"wir sind\s+([A-ZÄÖÜ][\w& ]+)", re.IGNORECASE)
_CITY_HINT_RE = re.compile(
    r"(?:city|ort|location)[:\-\s]+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\s-]+)",
    re.IGNORECASE,
)
_COMMON_CITIES = [
    "Berlin",
    "Düsseldorf",
    "Munich",
    "München",
    "Hamburg",
    "Stuttgart",
    "Frankfurt",
    "Cologne",
    "Köln",
    "Leipzig",
    "Bonn",
    "Essen",
    "Dortmund",
    "Dresden",
    "Nuremberg",
    "Nürnberg",
    "Hannover",
    "Bremen",
    "Mannheim",
    "Karlsruhe",
    "Münster",
]


def guess_job_title(text: str) -> str:
    """Return a basic job title guess from ``text``."""
    if not text:
        return ""
    first_line = text.strip().splitlines()[0]
    first_line = first_line.split("|")[0]
    first_line = re.split(r"\s[-–—]\s", first_line)[0]
    title = _GENDER_RE.sub("", first_line).strip()
    return title


def guess_company(text: str) -> Tuple[str, str]:
    """Guess company name and optional brand from ``text``."""
    if not text:
        return "", ""
    m = _BRAND_OF_RE.search(text)
    if m:
        brand, company = m.group(1).strip(), m.group(2).strip()
        return company, brand
    m = _COMPANY_FORM_RE.search(text)
    if m:
        return m.group(1).strip(), ""
    m = _WE_ARE_RE.search(text)
    if m:
        name = m.group(1).strip()
        return name, ""
    return "", ""


def guess_city(text: str) -> str:
    """Guess primary city from ``text``."""
    if not text:
        return ""
    m = _CITY_HINT_RE.search(text)
    if m:
        return m.group(1).split("|")[0].split(",")[0].strip()
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


def apply_basic_fallbacks(
    profile: NeedAnalysisProfile, text: str
) -> NeedAnalysisProfile:
    """Fill missing basic fields using heuristics."""
    if not profile.position.job_title:
        profile.position.job_title = guess_job_title(text)
    if not profile.company.name:
        name, brand = guess_company(text)
        if name:
            profile.company.name = name
        if brand and not profile.company.brand_name:
            profile.company.brand_name = brand
    elif not profile.company.brand_name:
        _, brand = guess_company(text)
        if brand:
            profile.company.brand_name = brand
    if not profile.location.primary_city:
        profile.location.primary_city = guess_city(text)
    return profile
