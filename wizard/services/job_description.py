"""Job description generation services shared by the wizard and tools."""

from __future__ import annotations

import textwrap
from typing import Any, Mapping

from core.job_ad import JOB_AD_FIELDS
from core.schema import coerce_and_fill
from openai_utils import generate_job_ad

_SHORT_DRAFT_WIDTH = 260


def _default_target_audience(profile: Mapping[str, Any], lang: str) -> str:
    job_title = str(profile.get("position", {}).get("job_title") or "").strip()
    lang_code = (lang or "en").lower()
    if lang_code.startswith("de"):
        if job_title:
            return f"Kandidat:innen für {job_title}"
        return "Allgemeine Kandidat:innen"
    if job_title:
        return f"Candidates for {job_title}"
    return "General candidates"


def _build_short_draft(text: str) -> str:
    if not text:
        return ""
    return textwrap.shorten(" ".join(text.split()), width=_SHORT_DRAFT_WIDTH, placeholder="…")


def generate_job_description(
    profile_json: Mapping[str, Any],
    *,
    tone: str = "professional",
    lang: str = "en",
) -> dict[str, Any]:
    """Generate short + long job description drafts using the canonical generator."""

    profile = coerce_and_fill(profile_json).model_dump(mode="json")
    lang_code = str(lang or profile.get("lang") or "en")

    target_audience = profile.get("job_ad", {}).get("target_audience")
    if not isinstance(target_audience, str) or not target_audience.strip():
        target_audience = _default_target_audience(profile, lang_code)

    selected_fields = [field.key for field in JOB_AD_FIELDS]
    long_draft = generate_job_ad(
        profile,
        selected_fields,
        target_audience=target_audience,
        tone=tone,
        lang=lang_code,
    ).strip()
    short_draft = _build_short_draft(long_draft)

    drafts: list[dict[str, str]] = []
    if short_draft:
        drafts.append({"kind": "short", "text": short_draft, "lang": lang_code})
    if long_draft:
        drafts.append({"kind": "long", "text": long_draft, "lang": lang_code})

    return {"drafts": drafts, "target_audience": target_audience}
