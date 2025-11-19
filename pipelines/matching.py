"""Rule-based candidate matching pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import re
from typing import Any

__all__ = ["match_candidates"]


MUST_HAVE_WEIGHT = 60.0
NICE_TO_HAVE_WEIGHT = 20.0
EXPERIENCE_WEIGHT = 10.0
LOCATION_WEIGHT = 10.0
LANGUAGE_PENALTY_PER_MISS = 4.0

_NORMALISE_SPACES_RE = re.compile(r"\s+")

_SENIORITY_TO_YEARS: dict[str, float] = {
    "intern": 0.0,
    "working student": 0.5,
    "entry": 1.0,
    "junior": 2.0,
    "associate": 3.0,
    "mid": 4.0,
    "mid-level": 5.0,
    "professional": 5.0,
    "staff": 6.0,
    "senior": 6.0,
    "lead": 8.0,
    "principal": 10.0,
    "manager": 8.0,
    "head": 8.0,
    "director": 10.0,
    "vp": 12.0,
    "vice president": 12.0,
    "executive": 12.0,
    "c-level": 15.0,
    "cto": 15.0,
    "chief": 15.0,
}


def match_candidates(
    vacancy_json: Mapping[str, Any], candidate_summaries: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return structured match scores for candidates against a vacancy."""

    requirements = vacancy_json.get("requirements") or {}
    must_have = _normalise_terms(
        requirements.get("hard_skills_required", []) + requirements.get("soft_skills_required", [])
    )
    nice_to_have = _normalise_terms(
        requirements.get("hard_skills_optional", [])
        + requirements.get("soft_skills_optional", [])
        + requirements.get("tools_and_technologies", [])
    )
    required_languages = _normalise_terms(requirements.get("languages_required", []))
    optional_languages = _normalise_terms(requirements.get("languages_optional", []))

    vacancy_id = str(
        vacancy_json.get("vacancy_id")
        or vacancy_json.get("id")
        or vacancy_json.get("meta", {}).get("vacancy_id")
        or "vacancy-unknown"
    )

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    required_years = _infer_required_years(vacancy_json)
    location_info = vacancy_json.get("location") or {}
    work_policy = (vacancy_json.get("employment") or {}).get("work_policy") or ""
    remote_allowed = _normalise_token(work_policy) in {"remote", "hybrid", "flexible"}

    scored: list[dict[str, Any]] = []
    for candidate in candidate_summaries:
        scored.append(
            _score_candidate(
                candidate,
                must_have=must_have,
                nice_to_have=nice_to_have,
                required_languages=required_languages,
                optional_languages=optional_languages,
                required_years=required_years,
                location_info=location_info,
                remote_allowed=remote_allowed,
            )
        )

    scored.sort(key=lambda item: item["score"], reverse=True)

    return {
        "vacancy_id": vacancy_id,
        "candidates": scored,
        "meta": {"generated_at": generated_at, "model": "rule-based-matcher"},
    }


def _score_candidate(
    summary: Mapping[str, Any],
    *,
    must_have: list[str],
    nice_to_have: list[str],
    required_languages: list[str],
    optional_languages: list[str],
    required_years: float | None,
    location_info: Mapping[str, Any],
    remote_allowed: bool,
) -> dict[str, Any]:
    candidate_info = summary.get("candidate") or {}
    candidate_id = str(candidate_info.get("id") or "candidate-unknown")
    candidate_name = candidate_info.get("name")
    candidate_years = _coerce_float(candidate_info.get("total_years_experience"))
    candidate_location_raw = candidate_info.get("location")

    skill_set, skill_lookup = _extract_skills(summary.get("skills"))
    language_set = _extract_languages(summary.get("languages"))

    gaps: list[str] = []
    reasons: list[str] = []
    highlighted: list[str] = []
    score = 0.0

    score += _score_must_have(
        must_have,
        skill_set,
        skill_lookup,
        highlighted,
        gaps,
        reasons,
    )
    score += _score_nice_to_have(
        nice_to_have,
        skill_set,
        skill_lookup,
        highlighted,
        reasons,
    )
    score += _score_experience(
        required_years,
        candidate_years,
        gaps,
        reasons,
    )
    score += _score_location(
        location_info,
        candidate_location_raw,
        remote_allowed,
        gaps,
        reasons,
    )
    score -= _penalise_language_gaps(
        required_languages,
        optional_languages,
        language_set,
        gaps,
        reasons,
    )

    score = max(0.0, min(100.0, round(score, 1)))

    return {
        "candidate_id": candidate_id,
        "name": candidate_name,
        "score": score,
        "highlighted_skills": list(dict.fromkeys(highlighted))[:6],
        "gaps": gaps,
        "reasons": reasons,
    }


def _normalise_terms(values: Iterable[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        token = _normalise_token(value)
        if token:
            cleaned.append(token)
    return cleaned


def _normalise_token(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = _NORMALISE_SPACES_RE.sub(" ", value).strip()
        return trimmed or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _extract_skills(skills: Any) -> tuple[set[str], dict[str, str]]:
    skill_set: set[str] = set()
    lookup: dict[str, str] = {}
    if not skills:
        return skill_set, lookup
    for entry in skills:
        if isinstance(entry, Mapping):
            label = entry.get("name") or entry.get("label")
        else:
            label = entry
        token = _normalise_token(label)
        if not token:
            continue
        norm = token.casefold()
        skill_set.add(norm)
        lookup.setdefault(norm, token)
    return skill_set, lookup


def _extract_languages(languages: Any) -> set[str]:
    lang_set: set[str] = set()
    if not languages:
        return lang_set
    for entry in languages:
        token: str | None = None
        if isinstance(entry, Mapping):
            token = _normalise_token(entry.get("code") or entry.get("name"))
        else:
            token = _normalise_token(entry)
        if not token:
            continue
        lang_set.add(token.casefold())
    return lang_set


def _score_must_have(
    must_have: list[str],
    skill_set: set[str],
    skill_lookup: Mapping[str, str],
    highlighted: list[str],
    gaps: list[str],
    reasons: list[str],
) -> float:
    if not must_have:
        reasons.append("No must-have skills specified for this role.")
        return MUST_HAVE_WEIGHT

    normalized = [skill.casefold() for skill in must_have]
    matched = [skill for skill in normalized if skill in skill_set]
    missing = [must_have[idx] for idx, skill in enumerate(normalized) if skill not in skill_set]

    highlighted.extend(
        skill_lookup.get(skill, must_have[idx]) for idx, skill in enumerate(normalized) if skill in skill_set
    )

    if missing:
        gaps.extend(f"Missing must-have skill: {item}" for item in missing)

    coverage = len(matched) / len(must_have)
    base_score = coverage * MUST_HAVE_WEIGHT
    penalty = 0.0
    if missing:
        penalty = min(
            MUST_HAVE_WEIGHT,
            len(missing) * (MUST_HAVE_WEIGHT / len(must_have)) * 1.5,
        )
    reasons.append(f"Matched {len(matched)}/{len(must_have)} must-have skills with {len(missing)} gap(s).")
    return base_score - penalty


def _score_nice_to_have(
    nice_to_have: list[str],
    skill_set: set[str],
    skill_lookup: Mapping[str, str],
    highlighted: list[str],
    reasons: list[str],
) -> float:
    if not nice_to_have:
        return 0.0
    normalized = [skill.casefold() for skill in nice_to_have]
    matched = [skill for skill in normalized if skill in skill_set]
    highlighted.extend(
        skill_lookup.get(skill, nice_to_have[idx]) for idx, skill in enumerate(normalized) if skill in skill_set
    )
    coverage = len(matched) / len(nice_to_have)
    reasons.append(f"Matched {len(matched)}/{len(nice_to_have)} nice-to-have skills.")
    return coverage * NICE_TO_HAVE_WEIGHT


def _score_experience(
    required_years: float | None,
    candidate_years: float | None,
    gaps: list[str],
    reasons: list[str],
) -> float:
    if required_years is None:
        if candidate_years is None:
            reasons.append("Experience not provided and no target specified.")
            return EXPERIENCE_WEIGHT * 0.5
        reasons.append(f"Candidate reports {candidate_years:.1f} years of experience.")
        return EXPERIENCE_WEIGHT

    if candidate_years is None:
        gaps.append(f"Missing total experience; expected ≥{required_years:.1f} years.")
        reasons.append("Experience missing for comparison.")
        return EXPERIENCE_WEIGHT * 0.2

    ratio = min(candidate_years / required_years, 1.2)
    if candidate_years < required_years:
        gaps.append(f"Requires {required_years:.1f}+ years; candidate has {candidate_years:.1f}.")
    reasons.append(f"Experience alignment: {candidate_years:.1f} years vs {required_years:.1f} expected.")
    return min(ratio, 1.0) * EXPERIENCE_WEIGHT


def _score_location(
    location_info: Mapping[str, Any],
    candidate_location_raw: Any,
    remote_allowed: bool,
    gaps: list[str],
    reasons: list[str],
) -> float:
    city = _normalise_token(location_info.get("primary_city")) if location_info else None
    country = _normalise_token(location_info.get("country")) if location_info else None

    if not city and not country:
        reasons.append("Location not specified for the vacancy.")
        return LOCATION_WEIGHT * 0.6

    candidate_location = _normalise_token(candidate_location_raw)

    if not candidate_location:
        if remote_allowed:
            reasons.append("Candidate location unknown but remote/hybrid allowed.")
            return LOCATION_WEIGHT * 0.4
        gaps.append("Candidate location missing; onsite presence expected.")
        return LOCATION_WEIGHT * 0.1

    candidate_norm = candidate_location.casefold()
    if city and city.casefold() in candidate_norm:
        reasons.append("Candidate located in the target city.")
        return LOCATION_WEIGHT
    if country and country.casefold() in candidate_norm:
        reasons.append("Candidate matches the target country.")
        return LOCATION_WEIGHT * 0.85
    if remote_allowed:
        reasons.append("Location mismatch offset by remote-friendly policy.")
        return LOCATION_WEIGHT * 0.5

    gaps.append(
        "Candidate located in {candidate_location} while role targets {target}.".format(
            candidate_location=candidate_location,
            target=city or country or "specific region",
        )
    )
    return LOCATION_WEIGHT * 0.1


def _penalise_language_gaps(
    required_languages: list[str],
    optional_languages: list[str],
    language_set: set[str],
    gaps: list[str],
    reasons: list[str],
) -> float:
    penalty = 0.0
    if required_languages:
        missing = [lang for lang in required_languages if lang.casefold() not in language_set]
        if missing:
            for lang in missing:
                gaps.append(f"Missing required language: {lang}.")
            penalty += LANGUAGE_PENALTY_PER_MISS * len(missing)
        reasons.append(f"Languages met: {len(required_languages) - len(missing)}/{len(required_languages)} required.")
    if optional_languages:
        matched = [lang for lang in optional_languages if lang.casefold() in language_set]
        reasons.append(f"Optional languages covered: {len(matched)}/{len(optional_languages)}.")
    return penalty


def _infer_required_years(vacancy_json: Mapping[str, Any]) -> float | None:
    requirements = vacancy_json.get("requirements") or {}
    explicit = requirements.get("years_experience") or requirements.get("min_years_experience")
    candidate = _coerce_float(explicit)
    if candidate is not None:
        return candidate

    position = vacancy_json.get("position") or {}
    seniority = _normalise_token(position.get("seniority_level") or position.get("seniority"))
    if not seniority:
        return None
    return _SENIORITY_TO_YEARS.get(seniority.casefold())


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
