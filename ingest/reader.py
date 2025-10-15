"""Read and normalize job posting text from multiple sources."""

from __future__ import annotations

import re
from pathlib import Path

from ingest.extractors import extract_text_from_file, extract_text_from_url
from ingest.types import ContentBlock, StructuredDocument, build_plain_text_document


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

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-/]{5,}\d")
_CONTACT_LABEL_RE = re.compile(
    r"(kontakt|contact|homepage|telefon|phone|e-?mail)\s*[:–—-]"
)


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


def _normalize_block_text(text: str) -> str:
    cleaned = strip_boilerplate(text or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_table_block(block: ContentBlock) -> ContentBlock | None:
    metadata = block.metadata or {}
    rows = metadata.get("rows", [])
    cleaned_rows: list[list[str]] = []
    for row in rows:
        cleaned_row = [_normalize_inline_text(cell) for cell in row]
        if any(cell for cell in cleaned_row):
            cleaned_rows.append(cleaned_row)
    if not cleaned_rows:
        return None
    new_meta = dict(metadata)
    new_meta["rows"] = cleaned_rows
    table_text = "\n".join(" | ".join(row) for row in cleaned_rows)
    return ContentBlock(
        type="table",
        text=table_text,
        level=block.level,
        metadata=new_meta,
    )


def clean_structured_document(doc: StructuredDocument) -> StructuredDocument:
    """Apply :func:`clean_job_text` rules to a structured document."""

    if not doc.text and not doc.blocks:
        return StructuredDocument(text="", blocks=[], source=doc.source)

    cleaned_text = clean_job_text(doc.text)
    cleaned_blocks: list[ContentBlock] = []
    for block in doc.blocks:
        if block.type == "table":
            cleaned = _clean_table_block(block)
            if cleaned:
                cleaned_blocks.append(cleaned)
            continue
        normalized = _normalize_block_text(block.text)
        if not normalized:
            continue
        metadata = dict(block.metadata) if block.metadata else None
        cleaned_blocks.append(
            ContentBlock(
                type=block.type,
                text=normalized,
                level=block.level,
                metadata=metadata,
            )
        )

    if not cleaned_blocks:
        return StructuredDocument(text=cleaned_text, blocks=[], source=doc.source)

    combined = StructuredDocument.from_blocks(cleaned_blocks, source=doc.source)
    if cleaned_text and cleaned_text != combined.text:
        return StructuredDocument(
            text=cleaned_text,
            blocks=combined.blocks,
            source=doc.source,
        )
    return combined


def read_job_text(
    files: list[str],
    url: str | None = None,
    pasted: str | None = None,
) -> StructuredDocument:
    """Merge text from files, URL and pasted snippets."""

    documents: list[StructuredDocument] = []

    for name in files:
        path = Path(name)
        if not path.exists():
            continue
        try:
            with path.open("rb") as handle:
                doc = extract_text_from_file(handle)
        except ValueError as exc:
            message = str(exc).strip()
            suffix = path.suffix.lower()
            if suffix and "unsupported file type" in message.lower():
                raise ValueError(
                    f"{path.name}: unsupported file type – upload a PDF, DOCX or text file."
                ) from exc
            detail = f" ({message})" if message else ""
            raise ValueError(f"{path.name}: failed to read file.{detail}") from exc
        documents.append(clean_structured_document(doc))

    if url:
        try:
            documents.append(clean_structured_document(extract_text_from_url(url)))
        except ValueError as exc:
            message = str(exc).strip()
            detail = f" ({message})" if message else ""
            raise ValueError(
                f"Failed to fetch {url}. Check if the site is reachable or if access is blocked.{detail}"
            ) from exc

    if pasted:
        documents.append(
            clean_structured_document(
                build_plain_text_document(pasted, source="pasted"),
            )
        )

    seen_texts: set[str] = set()
    ordered: list[StructuredDocument] = []
    for doc in documents:
        key = doc.text.strip()
        if not key or key in seen_texts:
            continue
        seen_texts.add(key)
        ordered.append(doc)

    combined_blocks: list[ContentBlock] = []
    for doc in ordered:
        combined_blocks.extend(doc.blocks)

    if not combined_blocks:
        combined_text = "\n\n".join(doc.text for doc in ordered).strip()
        return StructuredDocument(text=combined_text, blocks=[], source="merged")

    combined = StructuredDocument.from_blocks(combined_blocks, source="merged")
    if ordered:
        combined_text = "\n\n".join(doc.text for doc in ordered).strip()
        if combined_text and combined_text != combined.text:
            combined = StructuredDocument(
                text=combined_text,
                blocks=combined.blocks,
                source="merged",
            )
    return combined
