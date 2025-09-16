"""Utility helpers for the Cognitive Needs app."""

from __future__ import annotations

import os
import re
from typing import Any, Mapping

from .url_utils import extract_text_from_url as extract_text_from_url
from .errors import display_error as display_error
from models import NeedAnalysisProfile


def merge_texts(*parts: str) -> str:
    """Combine multiple text fragments into one string.

    Empty or whitespace-only parts are ignored. Remaining fragments are
    joined using newline separators.

    Args:
        *parts: Arbitrary text snippets.

    Returns:
        Merged text.
    """

    cleaned = [p.strip() for p in parts if p and p.strip()]
    return "\n".join(cleaned)


def highlight_keywords(text: str, keywords: list[str]) -> str:
    """Highlight keywords in ``text`` with Markdown bold markers."""

    if not text or not keywords:
        return text
    pattern = re.compile("|".join([re.escape(k) for k in keywords]), re.IGNORECASE)
    return pattern.sub(lambda m: f"**{m.group(0)}**", text)


def build_boolean_query(
    job_title: str,
    skills: list[str],
    *,
    include_title: bool = True,
    title_synonyms: list[str] | None = None,
) -> str:
    """Compose a Boolean search string from title and skills.

    Args:
        job_title: The main job title.
        skills: Skills to include in the query.
        include_title: Whether to include the job title and synonyms.
        title_synonyms: Additional job title synonyms.

    Returns:
        A Boolean search string combining title and skill terms.
    """

    title_terms: list[str] = []
    if include_title and job_title:
        title_terms.append(f'"{job_title}"')
    if include_title and title_synonyms:
        title_terms.extend(f'"{syn.strip()}"' for syn in title_synonyms if syn.strip())

    skill_terms = [f'"{s.strip()}"' for s in skills if s.strip()]
    title_query = " OR ".join(title_terms)

    if title_query and skill_terms:
        skill_clause = ") AND (".join(skill_terms)
        return f"({title_query}) AND ({skill_clause})"
    if title_query:
        return f"({title_query})"
    if skill_terms:
        return " AND ".join(f"({term})" for term in skill_terms)
    return ""


def build_boolean_search(data: Mapping[str, Any] | NeedAnalysisProfile) -> str:
    """Build a Boolean search string from profile data.

    Args:
        data: Profile mapping or :class:`NeedAnalysisProfile` instance.

    Returns:
        Boolean search string combining the job title and gathered skills.
    """

    profile = (
        data if isinstance(data, NeedAnalysisProfile) else NeedAnalysisProfile(**data)
    )
    job_title = profile.position.job_title or ""
    combined = (
        profile.requirements.hard_skills_required
        + profile.requirements.hard_skills_optional
        + profile.requirements.soft_skills_required
        + profile.requirements.soft_skills_optional
        + profile.requirements.tools_and_technologies
    )
    skills: list[str] = []
    seen: set[str] = set()
    for s in combined:
        key = s.strip()
        low = key.lower()
        if low and low not in seen:
            seen.add(low)
            skills.append(key)
    return build_boolean_query(job_title, skills)


def seo_optimize(text: str, max_keywords: int = 5) -> dict:
    """Basic SEO analysis returning keywords and a meta description."""

    result = {"keywords": [], "meta_description": ""}
    if not text:
        return result
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq, key=lambda k: freq[k], reverse=True)
    result["keywords"] = [w for w in top_words[:max_keywords]]
    first_sentence_end = re.search(r"[.!?]", text)
    if first_sentence_end:
        first_sentence = text[: first_sentence_end.end()]
    else:
        first_sentence = text[:160]
    if len(first_sentence) > 160:
        first_sentence = first_sentence[:157] + "..."
    result["meta_description"] = first_sentence.strip()
    return result


def ensure_logs_dir() -> None:
    """Create the logs directory if it does not exist."""

    try:
        os.makedirs("logs", exist_ok=True)
    except Exception:
        pass
