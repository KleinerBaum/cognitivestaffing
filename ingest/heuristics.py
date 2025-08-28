import re
from datetime import datetime
from typing import Optional, Tuple

from models.need_analysis import NeedAnalysisProfile

_GENDER_RE = re.compile(
    r"\s*\((?:[mwfd]\s*/){2}[mwfd]\)\s*|\s*all genders\s*",
    re.IGNORECASE,
)
_BRAND_OF_RE = re.compile(
    r"([A-ZÄÖÜ][\w& ]+?),\s+ein[^,]*?\s+der\s+([A-ZÄÖÜ][\w& ]+(?:GmbH|AG|Inc|Ltd|UG|KG))",
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

_JOB_TYPE_MAP = {
    "full_time": ["vollzeit", "full-time", "full time"],
    "part_time": ["teilzeit", "part-time", "part time"],
}

_CONTRACT_TYPE_MAP = {
    "permanent": ["festanstellung", "permanent", "unbefristet"],
    "fixed_term": ["befristet", "fixed-term", "temporary"],
}

_WORK_POLICY_MAP = {
    "remote": ["remote", "home office", "home-office", "homeoffice"],
    "hybrid": ["hybrid"],
}

_REMOTE_PERCENT_RE = re.compile(
    r"(\d{1,2})\s*%\s*(?:remote|home|home\s*office)", re.IGNORECASE
)
_REMOTE_DAYS_RE = re.compile(
    r"(\d)[–-](\d)\s*(?:Tage|days)\/Woche.*?(?:Office|Büro)|"
    r"(\d)\s*(?:Tage|days)\/Woche.*?(?:Office|Büro)",
    re.IGNORECASE,
)

_DATE_PATTERNS = [
    r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    r"\b(\d{4}-\d{2}-\d{2})\b",
]

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

_IMMEDIATE_RE = re.compile(r"ab\s+(sofort|immediately|asap)", re.IGNORECASE)


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

    remote_percentage: Optional[int] = None
    m = _REMOTE_PERCENT_RE.search(text)
    if m:
        remote_percentage = int(m.group(1))
    else:
        m = _REMOTE_DAYS_RE.search(text)
        if m:
            if m.group(3):
                office_days = float(m.group(3))
            else:
                day_a = int(m.group(1))
                day_b = int(m.group(2))
                office_days = (day_a + day_b) / 2
            remote_percentage = int(round((1 - office_days / 5) * 100))

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
        return m.group(1).lower()
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
    job, contract, policy, remote_pct = guess_employment_details(text)
    if not profile.employment.job_type and job:
        profile.employment.job_type = job
    if not profile.employment.contract_type and contract:
        profile.employment.contract_type = contract
    if not profile.employment.work_policy and policy:
        profile.employment.work_policy = policy
    if (
        remote_pct is not None
        and profile.employment.remote_percentage is None
        and profile.employment.work_policy in {"remote", "hybrid"}
    ):
        profile.employment.remote_percentage = remote_pct
    if not profile.meta.target_start_date:
        start = guess_start_date(text)
        if start:
            profile.meta.target_start_date = start
    return profile
