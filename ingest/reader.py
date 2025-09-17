"""Read and normalize job posting text from multiple sources."""

from __future__ import annotations

import re
from pathlib import Path

import fitz
from bs4 import BeautifulSoup
from docx import Document
import requests


_SPACE_RE = re.compile(r"\s+")
_NAV_SPLIT_RE = re.compile(r"[|>/»«·•→]+")
_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+", re.UNICODE)

_MENU_TOKENS = {
    "home",
    "karriere",
    "career",
    "jobs",
    "stellenangebote",
    "unternehmen",
    "company",
    "about",
    "team",
    "people",
    "culture",
    "benefits",
    "solutions",
    "services",
    "students",
    "graduates",
    "professionals",
    "kontakt",
    "contact",
    "news",
    "blog",
    "events",
    "search",
    "suche",
    "karriereportal",
    "stellenmarkt",
    "jobsuche",
    "apply",
    "bewerben",
    "bewerbung",
    "login",
    "logout",
    "register",
    "registrieren",
}

_LANGUAGE_TOKENS = {
    "deutsch",
    "german",
    "english",
    "englisch",
    "français",
    "französisch",
    "español",
    "spanisch",
    "italiano",
    "polski",
    "中文",
    "日本語",
}

_SOCIAL_TOKENS = {
    "linkedin",
    "facebook",
    "instagram",
    "youtube",
    "twitter",
    "xing",
    "whatsapp",
}

_SHORT_TOKENS = {
    "faq",
    "jobs",
    "job",
    "karriere",
    "career",
    "about",
    "team",
    "people",
    "news",
    "blog",
    "events",
    "apply",
    "bewerben",
    "bewerbung",
    "login",
    "logout",
    "register",
    "kontakt",
    "contact",
    "search",
    "suche",
    "portal",
    "jobsuche",
    "students",
    "graduates",
    "professionals",
    "benefits",
}

_SINGLE_WORD_REMOVALS = {
    "menu",
    "menü",
    "navigation",
    "nav",
    "schließen",
    "schliessen",
    "close",
    "zurück",
    "back",
}

_CTA_LINES = {
    "apply now",
    "apply now!",
    "apply online",
    "jetzt bewerben",
    "jetzt bewerben!",
    "jetzt online bewerben",
    "jetzt informieren",
    "job merken",
    "stelle merken",
    "job teilen",
    "share job",
    "share this job",
    "jetzt teilen",
}

_FOOTER_KEYWORDS = {
    "privacy",
    "privacy policy",
    "datenschutz",
    "impressum",
    "cookie",
    "agb",
    "terms",
    "bedingungen",
    "all rights reserved",
    "equal opportunity employer",
}

_BOILERPLATE_CONTAINS = {
    "skip to main content",
    "zum hauptinhalt",
    "zur hauptnavigation",
    "toggle navigation",
    "karriereportal",
    "bewerber-login",
    "bewerberlogin",
    "candidate login",
    "follow us",
    "folgen sie uns",
    "teilen auf",
    "zurück zur jobsuche",
    "zur jobübersicht",
    "zur jobuebersicht",
    "zur stellenauswahl",
    "jetzt teilen",
    "jetzt bewerben",
}


def _read_txt(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def _read_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_pdf(path: Path) -> str:
    with fitz.open(path) as doc:
        return "".join(page.get_text() for page in doc)


_URL_RE = re.compile(r"^https?://[\w./-]+$")
_HEADERS = {"User-Agent": "CognitiveNeeds/1.0"}

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-/]{5,}\d")
_CONTACT_LABEL_RE = re.compile(r"(kontakt|contact|homepage|telefon|phone|e-?mail)\s*[:–—-]")


def _read_url(url: str) -> str:
    if not url or not _URL_RE.match(url):
        raise ValueError("Invalid URL")
    try:
        response = requests.get(url, timeout=15, headers=_HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network
        raise ValueError(f"Failed to fetch URL: {url}") from exc
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text(" ")


def _normalize_for_check(text: str) -> str:
    """Return ``text`` lowercased with collapsed whitespace."""

    return _SPACE_RE.sub(" ", text).strip().lower()


def _looks_like_navigation(line: str) -> bool:
    """Return ``True`` if ``line`` resembles navigation or footer boilerplate."""

    stripped = line.strip()
    if not stripped:
        return False
    normalized = _normalize_for_check(stripped)
    if not normalized:
        return False
    if normalized in _CTA_LINES:
        return True
    if any(phrase in normalized for phrase in _BOILERPLATE_CONTAINS):
        return True
    if normalized.startswith("©") or normalized.startswith("(c)"):
        return True
    if ("cookie" in normalized or "all rights reserved" in normalized) and len(
        normalized
    ) <= 160:
        return True
    if (
        any(keyword in normalized for keyword in _FOOTER_KEYWORDS)
        and len(normalized) <= 160
    ):
        return True
    has_email = bool(_EMAIL_RE.search(stripped))
    has_phone = bool(_PHONE_RE.search(stripped))
    has_contact_label = bool(_CONTACT_LABEL_RE.search(normalized))
    if re.search(r"https?://|www\.\w", normalized):
        if has_contact_label or has_email or has_phone:
            return False
        return True

    tokens = _WORD_RE.findall(normalized)
    if tokens:
        if len(tokens) >= 3:
            known = sum(
                1
                for tok in tokens
                if tok in _MENU_TOKENS
                or tok in _LANGUAGE_TOKENS
                or tok in _SOCIAL_TOKENS
                or tok in _SHORT_TOKENS
            )
            if known / len(tokens) >= 0.7:
                return True
        joined = " ".join(tokens)
        if joined in _CTA_LINES:
            return True
        if len(tokens) == 1 and tokens[0] in _SINGLE_WORD_REMOVALS:
            return True

    if (
        stripped.count("|") >= 2
        or stripped.count(">") >= 2
        or stripped.count("/") >= 2
        or stripped.count("•") >= 3
    ):
        segments = [
            seg.strip().lower() for seg in _NAV_SPLIT_RE.split(stripped) if seg.strip()
        ]
        if segments:
            known = sum(
                1
                for seg in segments
                if seg in _MENU_TOKENS
                or seg in _LANGUAGE_TOKENS
                or seg in _SOCIAL_TOKENS
                or seg in _SHORT_TOKENS
            )
            if known / len(segments) >= 0.6 or len(segments) >= 5:
                return True
    return False


def strip_boilerplate(text: str) -> str:
    """Remove boilerplate navigation/footer lines from ``text``."""

    if not text:
        return ""
    cleaned_lines: list[str] = []
    for raw_line in text.replace("\u00a0", " ").replace("\ufeff", "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            cleaned_lines.append("")
            continue
        if _looks_like_navigation(line):
            continue
        cleaned_lines.append(line.strip())

    result: list[str] = []
    for line in cleaned_lines:
        if not line:
            if result and result[-1] == "":
                continue
            if not result:
                continue
            result.append("")
        else:
            result.append(line)
    return "\n".join(result).strip()


def clean_job_text(text: str) -> str:
    """Normalize whitespace and remove boilerplate from job posting text."""

    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = strip_boilerplate(normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()


def read_job_text(
    files: list[str],
    url: str | None = None,
    pasted: str | None = None,
) -> str:
    """Merge text from files, URL and pasted snippets.

    Args:
        files: Paths to local files (PDF, DOCX, TXT).
        url: Optional web URL to fetch.
        pasted: Additional pasted text.

    Returns:
        Cleaned and de-duplicated text.
    """

    texts: list[str] = []
    for name in files:
        path = Path(name)
        suffix = path.suffix.lower()
        content = ""
        if suffix == ".pdf":
            content = _read_pdf(path)
        elif suffix == ".docx":
            content = _read_docx(path)
        elif suffix == ".txt":
            content = _read_txt(path)
        if content:
            cleaned = clean_job_text(content)
            if cleaned:
                texts.append(cleaned)

    if url:
        cleaned = clean_job_text(_read_url(url))
        if cleaned:
            texts.append(cleaned)
    if pasted:
        cleaned = clean_job_text(pasted)
        if cleaned:
            texts.append(cleaned)

    unique = list(dict.fromkeys(texts))
    return "\n\n".join(unique)
