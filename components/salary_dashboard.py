"""Sidebar salary analytics dashboard component."""

from typing import Any, Final, Sequence, Tuple

import streamlit as st
from config import OPENAI_MODEL


# ``openai_utils`` is an optional dependency. Import lazily so that the
# dashboard still renders even if the OpenAI helper is unavailable (e.g.,
# during tests without the SDK installed).
def _call_chat_api(messages: list[dict], **kwargs: Any) -> str:
    """Lazy import wrapper around ``openai_utils.call_chat_api``."""
    from openai_utils import call_chat_api

    if "model" not in kwargs:
        kwargs["model"] = st.session_state.get("model", OPENAI_MODEL)
    res = call_chat_api(messages, **kwargs)
    return (res.content or "") if hasattr(res, "content") else str(res)


SENIORITY_LEVELS: Final[tuple[tuple[tuple[str, ...], float], ...]] = (
    (("intern", "werkstudent", "working_student"), 0.65),
    (("junior",), 0.85),
    (("mid", "professional", "experienced"), 1.0),
    (("senior",), 1.25),
    (("lead", "principal"), 1.35),
    (("head", "director"), 1.55),
    (("vp", "vice president"), 1.75),
    (("chief", "c-level"), 2.0),
)

LOCATION_FACTOR: Final[dict[str, float]] = {
    "berlin": 1.05,
    "munich": 1.15,
    "hamburg": 1.08,
    "frankfurt": 1.12,
    "stuttgart": 1.1,
    "cologne": 1.04,
    "dusseldorf": 1.04,
    "remote": 0.95,
}

INDUSTRY_MULTIPLIERS: Final[tuple[tuple[tuple[str, ...], float], ...]] = (
    (("technology", "software", "tech"), 1.15),
    (("finance", "bank", "insurance", "fintech"), 1.12),
    (("consulting", "professional services"), 1.08),
    (("pharma", "biotech", "medical"), 1.1),
    (("manufacturing", "industrial"), 0.95),
    (("nonprofit", "ngo", "charity"), 0.85),
    (("education", "academia"), 0.9),
    (("retail", "hospitality"), 0.9),
)

JOB_TITLE_BASELINES: Final[tuple[tuple[tuple[str, ...], float], ...]] = (
    (("data", "scientist"), 78000.0),
    (("machine", "learning"), 82000.0),
    (("data", "engineer"), 76000.0),
    (("software", "engineer"), 72000.0),
    (("full", "stack"), 73000.0),
    (("backend",), 70000.0),
    (("frontend",), 68000.0),
    (("devops",), 78000.0),
    (("cloud",), 75000.0),
    (("security",), 80000.0),
    (("product", "manager"), 85000.0),
    (("project", "manager"), 65000.0),
    (("engineering", "manager"), 95000.0),
    (("qa", "quality"), 56000.0),
    (("designer",), 60000.0),
    (("marketing",), 58000.0),
    (("sales",), 55000.0),
    (("recruiter", "talent"), 52000.0),
    (("consultant",), 65000.0),
    (("analyst",), 60000.0),
)

DEFAULT_BASE_SALARY: Final[float] = 54000.0
CONTRACT_JOB_TYPES: Final[set[str]] = {
    "contract",
    "freelance",
    "temporary",
    "consulting",
}
ANNUAL_WORKING_HOURS: Final[float] = 1680.0
SKILL_WEIGHT_MUST: Final[float] = 0.02
SKILL_WEIGHT_NICE: Final[float] = 0.01
TASK_WEIGHT: Final[float] = 0.012
LANGUAGE_WEIGHT: Final[float] = 0.03
MAX_SKILL_PREMIUM: Final[float] = 0.35
MAX_TASK_PREMIUM: Final[float] = 0.18
MAX_LANGUAGE_PREMIUM: Final[float] = 0.09


def _normalize_text(value: str | None) -> str:
    """Normalize free-text fields for keyword comparisons."""

    if not value:
        return ""
    return value.strip().lower()


def _base_salary_for_job_title(job_title: str) -> float:
    """Return a benchmark base salary derived from the job title."""

    normalized = _normalize_text(job_title)
    for keywords, base in JOB_TITLE_BASELINES:
        if all(keyword in normalized for keyword in keywords):
            return base
    return DEFAULT_BASE_SALARY


def _seniority_multiplier(seniority: str, job_title: str) -> float:
    """Estimate a multiplier derived from the seniority and job title."""

    normalized_seniority = _normalize_text(seniority)
    normalized_title = _normalize_text(job_title)
    for keywords, multiplier in SENIORITY_LEVELS:
        if any(keyword in normalized_seniority for keyword in keywords) or any(
            keyword in normalized_title for keyword in keywords
        ):
            return multiplier
    return 1.0


def _location_multiplier(location: str) -> float:
    """Estimate a location-based multiplier with fuzzy matching."""

    normalized = _normalize_text(location)
    for key, factor in LOCATION_FACTOR.items():
        if key in normalized:
            return factor
    return 1.0


def _industry_multiplier(industry: str) -> float:
    """Return a multiplier based on the hiring company's industry."""

    normalized = _normalize_text(industry)
    if not normalized:
        return 1.0
    for keywords, multiplier in INDUSTRY_MULTIPLIERS:
        if any(keyword in normalized for keyword in keywords):
            return multiplier
    return 1.0


def _skill_multiplier(must_skills: Sequence[str], nice_skills: Sequence[str]) -> float:
    """Compute a multiplier based on required and optional skills."""

    premium = len(must_skills) * SKILL_WEIGHT_MUST
    premium += len(nice_skills) * SKILL_WEIGHT_NICE
    premium = min(MAX_SKILL_PREMIUM, premium)
    return 1.0 + premium


def _task_multiplier(tasks: Sequence[str]) -> float:
    """Compute a multiplier reflecting scope and complexity of tasks."""

    premium = min(MAX_TASK_PREMIUM, len(tasks) * TASK_WEIGHT)
    return 1.0 + premium


def _language_multiplier(languages: Sequence[str]) -> float:
    """Compute a multiplier rewarding multi-language requirements."""

    additional_languages = max(0, len(languages) - 1)
    premium = min(MAX_LANGUAGE_PREMIUM, additional_languages * LANGUAGE_WEIGHT)
    return 1.0 + premium


def _is_contract_job(job_type: str) -> bool:
    """Return whether the given job type represents contract work."""

    normalized = _normalize_text(job_type)
    return normalized in CONTRACT_JOB_TYPES


def compute_expected_salary(
    must_skills: Sequence[str],
    nice_skills: Sequence[str],
    seniority: str,
    location: str,
    job_type: str,
    job_title: str,
    tasks: Sequence[str],
    languages: Sequence[str],
    company_industry: str,
) -> Tuple[float, str]:
    """Estimate expected salary or hourly rate.

    Args:
        must_skills: Must-have skills.
        nice_skills: Nice-to-have skills.
        seniority: Seniority level.
        location: Job location.
        job_type: Type of contract, e.g., "permanent" or "contract".
        job_title: Job title or role name.
        tasks: Responsibilities associated with the role.
        languages: Languages required or optional for the role.
        company_industry: Industry classification of the employer.

    Returns:
        Tuple containing the numeric value and mode ("annual" or "hourly").
    """

    base_salary = _base_salary_for_job_title(job_title)
    seniority_factor = _seniority_multiplier(seniority, job_title)
    location_factor = _location_multiplier(location)
    industry_factor = _industry_multiplier(company_industry)
    skill_factor = _skill_multiplier(must_skills, nice_skills)
    task_factor = _task_multiplier(tasks)
    language_factor = _language_multiplier(languages)

    annual_value = (
        base_salary
        * seniority_factor
        * location_factor
        * skill_factor
        * task_factor
        * language_factor
        * industry_factor
    )

    if _is_contract_job(job_type):
        hourly_rate = annual_value / ANNUAL_WORKING_HOURS
        return round(hourly_rate, 2), "hourly"

    return round(annual_value), "annual"


def _session_list(session_state: Any, key: str) -> list[str]:
    """Extract a clean list of strings from session state.

    Args:
        session_state: Session state or mapping containing stored values.
        key: Target key in the mapping.

    Returns:
        List of non-empty, stripped strings.
    """

    raw = session_state.get(key, "")
    if isinstance(raw, str):
        return [s.strip() for s in raw.splitlines() if s.strip()]
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    return []


def render_salary_dashboard(session_state: Any) -> None:
    """Render salary analytics widget in the sidebar.

    Args:
        session_state: Streamlit session state used to fetch profile data.
    """

    must_skills = _session_list(
        session_state, "requirements.hard_skills_required"
    ) + _session_list(session_state, "requirements.soft_skills_required")
    nice_skills = _session_list(
        session_state, "requirements.hard_skills_optional"
    ) + _session_list(session_state, "requirements.soft_skills_optional")
    seniority = session_state.get("position.seniority_level", "")
    location = session_state.get("location.primary_city", "")
    job_type = session_state.get("employment.job_type", "permanent")
    job_title = session_state.get("position.job_title", "")
    tasks = _session_list(session_state, "responsibilities.items")
    languages = _session_list(
        session_state, "requirements.languages_required"
    ) + _session_list(session_state, "requirements.languages_optional")
    company_industry = session_state.get("company.industry", "")

    value, mode = compute_expected_salary(
        must_skills,
        nice_skills,
        seniority,
        location,
        job_type,
        job_title,
        tasks,
        languages,
        company_industry,
    )
    unit = "€/year" if mode == "annual" else "€/hour"

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='text-align:center;font-size:3rem'>💰</div>"  # noqa: E501
        f"<div style='text-align:center;font-size:1.5rem;font-weight:bold'>"
        f"{value:,.2f} {unit}</div>",
        unsafe_allow_html=True,
    )

    st.sidebar.caption(
        "Prognose basierend auf {context}. Aufgaben: {tasks}, Skills: {skills}, Sprachen: {languages}.".format(
            context=", ".join(
                [
                    value
                    for value in [job_title, seniority, location]
                    if value and value.strip()
                ]
            )
            or "verfügbaren Angaben",
            tasks=len(tasks),
            skills=len(must_skills) + len(nice_skills),
            languages=len(languages),
        )
    )

    length = st.sidebar.selectbox(
        "Explanation length",
        ["short", "medium", "long"],
        key="salary_explanation_length",
    )
    if st.sidebar.button("Explain factors"):
        prompt = (
            "You are a compensation analyst.\n"
            + f"Job title: {job_title or 'N/A'}\n"
            + f"Location: {location or 'N/A'}\n"
            + f"Seniority: {seniority or 'N/A'}\n"
            + f"Contract type: {job_type or 'N/A'}\n"
            + f"Must-have skills: {', '.join(must_skills) or 'none'}\n"
            + f"Nice-to-have skills: {', '.join(nice_skills) or 'none'}\n"
            + f"Key responsibilities: {', '.join(tasks) or 'none'}\n"
            + f"Languages: {', '.join(languages) or 'none'}\n"
            + "Explain the factors affecting the expected salary in a "
            f"{length} explanation."
        )
        try:
            explanation = _call_chat_api(
                [{"role": "user", "content": prompt}], max_tokens=300
            )
            st.sidebar.info(explanation)
        except Exception as exc:  # pragma: no cover - network failure
            st.sidebar.error(str(exc))
