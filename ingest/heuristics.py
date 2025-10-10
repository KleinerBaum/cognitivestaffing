import re
from datetime import datetime
from typing import List, Mapping, MutableMapping, Optional, Sequence, Tuple

from models.need_analysis import NeedAnalysisProfile, Requirements
from nlp.entities import extract_location_entities
from utils.normalization import normalize_country, normalize_language_list

# Matches gender suffixes appended to job titles such as "(m/w/d)" or "all genders".
# Handles German abbreviations (m/w/d, m/w/x, etc.) separated by slashes and ignores
# optional punctuation before the suffix.
_GENDER_RE = re.compile(
    r"(?P<prefix>\s*[-–—:,/|]*)?(?P<suffix>\((?:[mwfd]\s*/\s*){2}[mwfd]\)|all genders)",
    re.IGNORECASE,
)
# Finds gender suffixes at the very end of a line so we can strip trailing markers like
# "Junior Developer (m/w/d)" without affecting inline occurrences.
_GENDER_SUFFIX_END_RE = re.compile(
    r"(?:\((?:[mwfd]\s*/\s*){2}[mwfd]\)|all genders)\s*$",
    re.IGNORECASE,
)
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

_LOCATION_KEYWORD_NORMALIZED = {
    re.sub(r"[\W_]+", "", keyword).casefold() for keyword in _LOCATION_KEYWORDS
}

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
    r"(?:Tag(?:e)?|day(?:s)?)\s*/\s*Woche[^\n]*?(?:remote|Home[-\s]*Office|von\s+zu\s+Hause|"
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
}
_LANGUAGE_MAP = {
    "English": ["english", "englisch"],
    "German": ["german", "deutsch"],
    "French": ["french", "französisch"],
    "Spanish": ["spanish", "spanisch"],
}
_TECH_KEYWORDS = {
    "python",
    "docker",
    "aws",
    "faiss",
    "sql",
}
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
    "hauptaufgaben",
    "ihre aufgaben",
    "ihre verantwortlichkeiten",
    "key responsibilities",
    "main tasks",
    "responsibilities",
    "was dich bei uns erwartet",
    "was dich erwartet",
    "your responsibilities",
    "your tasks",
    "what you'll do",
    "duties",
}


_BENEFIT_HEADINGS = {
    "benefits",
    "benefit",
    "unsere benefits",
    "deine benefits",
    "our benefits",
    "perks",
    "perks & benefits",
    "perks and benefits",
    "what we offer",
    "what you get",
    "was wir bieten",
    "was wir dir bieten",
    "was wir ihnen bieten",
    "unsere vorteile",
    "deine vorteile",
    "vorteile",
    "leistungen",
}

_BENEFIT_SEP_RE = re.compile(r"[•,;\n]+")


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


def _match_benefit_heading(line: str) -> Tuple[bool, str]:
    """Return ``(True, trailing)`` if ``line`` is a benefit heading."""

    stripped = line.strip()
    if not stripped:
        return False, ""
    parts = re.split(r"[:：]", stripped, maxsplit=1)
    heading_norm = re.sub(r"\s+", " ", parts[0]).strip(" -–—•\t").lower()
    if heading_norm in _BENEFIT_HEADINGS:
        trailing = parts[1].strip() if len(parts) > 1 else ""
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
    requirements.hard_skills_optional = _dedupe_secondary(
        requirements.hard_skills_optional, hard_req_markers
    )
    requirements.soft_skills_optional = _dedupe_secondary(
        requirements.soft_skills_optional, soft_req_markers
    )


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
            lower = item.lower()
            for tech in _TECH_KEYWORDS:
                if re.search(rf"\b{re.escape(tech)}\b", lower):
                    techs.add(tech)
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


def refine_requirements(profile: NeedAnalysisProfile, text: str) -> NeedAnalysisProfile:
    """Enrich ``profile.requirements`` using heuristics from ``text``."""

    _split_soft_from_hard(profile)
    _extract_tools_from_lists(profile)

    req_bullets, opt_bullets = _extract_requirement_bullets(text)
    hard_req: List[str] = []
    soft_req: List[str] = []
    hard_opt: List[str] = []
    soft_opt: List[str] = []
    for item in req_bullets:
        if _is_soft_skill(item):
            soft_req.append(item)
        else:
            hard_req.append(item)
    for item in opt_bullets:
        if _is_soft_skill(item):
            soft_opt.append(item)
        else:
            hard_opt.append(item)

    r = profile.requirements
    r.languages_required = normalize_language_list(r.languages_required)
    r.languages_optional = normalize_language_list(r.languages_optional)
    r.hard_skills_required = _merge_unique(r.hard_skills_required, hard_req)
    r.hard_skills_optional = _merge_unique(r.hard_skills_optional, hard_opt)
    r.soft_skills_required = _merge_unique(r.soft_skills_required, soft_req)
    r.soft_skills_optional = _merge_unique(r.soft_skills_optional, soft_opt)

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
    return profile


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
            if (lower in _RESP_HEADINGS or line.endswith(":")) and not _is_bullet_line(
                line
            ):
                break
            if _is_bullet_line(line):
                items.append(_clean_bullet(raw_line))
            elif items:
                items[-1] += f" {line}"
        elif lower in _RESP_HEADINGS:
            in_section = True
    return [i for i in items if i]


def _line_ends_with_gender_marker(line: str) -> bool:
    return bool(_GENDER_SUFFIX_END_RE.search(line.strip()))


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

    normalized = _GENDER_RE.sub(_replace, title)
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
        if all(
            _is_location_token(segment, known_locations) or _POSTAL_CODE_RE.search(segment)
            for segment in segments
        ):
            return True
    segments = [seg.strip() for seg in re.split(r"[|/•·,]", stripped) if seg.strip()]
    if len(segments) > 1:
        if all(
            _is_location_token(segment, known_locations)
            or _POSTAL_CODE_RE.search(segment)
            or _segment_is_city(segment)
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
        _normalize_for_compare(value)
        for value in skip_phrases or []
        if isinstance(value, str) and value.strip()
    }
    location_values = {
        _normalize_for_compare(value)
        for value in known_locations or []
        if isinstance(value, str) and value.strip()
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
    invalid_fields = {
        field for field in metadata.get("invalid_fields", []) if isinstance(field, str)
    }
    high_confidence = {
        field
        for field in metadata.get("high_confidence_fields", [])
        if isinstance(field, str)
    }
    locked_fields = {
        field
        for field in metadata.get("locked_fields", [])
        if isinstance(field, str)
    }
    city_field = "location.primary_city"
    country_field = "location.country"
    city_invalid = city_field in invalid_fields
    country_invalid = country_field in invalid_fields

    def _needs_value(value: Optional[str], field: str) -> bool:
        if field in high_confidence and field not in invalid_fields:
            return False
        if field in invalid_fields:
            return True
        return not (value and value.strip())

    location_entities = None

    if not profile.position.job_title and "position.job_title" not in locked_fields:
        company_hints = _coerce_strings(
            [profile.company.name, profile.company.brand_name]
        )
        company_hints.extend(
            _collect_locked_values(metadata, "company.name", locked_fields)
        )
        company_hints.extend(
            _collect_locked_values(metadata, "company.brand_name", locked_fields)
        )
        location_hints = _coerce_strings(
            [profile.location.primary_city, profile.location.country]
        )
        location_hints.extend(
            _collect_locked_values(metadata, "location.primary_city", locked_fields)
        )
        location_hints.extend(
            _collect_locked_values(metadata, "location.country", locked_fields)
        )
        skip_phrases = company_hints + _collect_locked_values(
            metadata, "position.job_title", locked_fields
        )
        title_guess = guess_job_title(
            text,
            skip_phrases=skip_phrases,
            known_locations=location_hints,
        )
        if title_guess:
            profile.position.job_title = title_guess
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
    if _needs_value(profile.location.primary_city, city_field):
        # City fallback order: reuse regex-based guess_city first, then fall back to
        # spaCy entity extraction (if available) before retrying the regex when the
        # field is marked invalid.
        city_guess = "" if city_invalid else guess_city(text)
        if not city_guess or city_invalid:
            if location_entities is None:
                location_entities = extract_location_entities(text, lang=language_hint)
            if location_entities:
                spa_city = location_entities.primary_city or ""
            else:
                spa_city = ""
            if spa_city:
                city_guess = spa_city
            elif city_invalid:
                city_guess = guess_city(text)
        if city_guess:
            profile.location.primary_city = city_guess
    if _needs_value(profile.location.country, country_field):
        # Country fallback order mirrors the city logic: prefer spaCy geo entities and
        # only fall back to heuristics when no entity is found and the field was invalid.
        if location_entities is None:
            location_entities = extract_location_entities(text, lang=language_hint)
        if location_entities:
            country_guess = location_entities.primary_country or ""
        else:
            country_guess = ""
        if not country_guess and country_invalid:
            country_guess = ""
        if country_guess:
            profile.location.country = country_guess
    # Employment classification: regex heuristics via guess_employment_details decide
    # job type, contract type, work policy, and remote percentage before any manual
    # overrides.
    job, contract, policy, remote_pct = guess_employment_details(text)
    if not profile.employment.job_type and job:
        profile.employment.job_type = job
    if not profile.employment.contract_type and contract:
        profile.employment.contract_type = contract
    if not profile.employment.work_policy and policy:
        profile.employment.work_policy = policy
    if remote_pct is not None and profile.employment.remote_percentage is None:
        profile.employment.remote_percentage = remote_pct
    if not profile.meta.target_start_date:
        start = guess_start_date(text)
        if start:
            profile.meta.target_start_date = start
    if not profile.responsibilities.items:
        tasks = extract_responsibilities(text)
        if tasks:
            profile.responsibilities.items = tasks
    if not profile.position.role_summary and profile.responsibilities.items:
        profile.position.role_summary = profile.responsibilities.items[0]
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
    if not compensation.variable_pay:
        if re.search(
            r"variable|bonus|provision|prämie|commission", text, re.IGNORECASE
        ):
            compensation.variable_pay = True
        pct = _BONUS_PERCENT_RE.search(text)
        if pct:
            compensation.bonus_percentage = float(pct.group(1))
            compensation.variable_pay = True
        if compensation.variable_pay and not compensation.commission_structure:
            btxt = _BONUS_TEXT_RE.search(text)
            if btxt:
                compensation.commission_structure = btxt.group(0).strip()
    benefits = _extract_benefits_from_text(text)
    if benefits:
        existing_benefits = list(compensation.benefits or [])
        merged_benefits = _normalize_benefit_entries(existing_benefits + benefits)
        if merged_benefits:
            compensation.benefits = merged_benefits
            if isinstance(metadata, MutableMapping):
                locked = set(
                    str(field) for field in metadata.get("locked_fields", []) if isinstance(field, str)
                )
                locked.add("compensation.benefits")
                metadata["locked_fields"] = sorted(locked)
                high_conf = set(
                    str(field)
                    for field in metadata.get("high_confidence_fields", [])
                    if isinstance(field, str)
                )
                high_conf.add("compensation.benefits")
                metadata["high_confidence_fields"] = sorted(high_conf)
    country = normalize_country(profile.location.country)
    profile.location.country = country
    return refine_requirements(profile, text)
