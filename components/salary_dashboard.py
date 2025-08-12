"""Sidebar salary analytics dashboard component."""

import streamlit as st
from typing import Sequence, Tuple

from openai_utils import call_chat_api

SENIORITY_FACTOR = {"junior": 0.8, "mid": 1.0, "senior": 1.3}
LOCATION_FACTOR = {"berlin": 1.0, "munich": 1.2, "remote": 0.9}


def compute_expected_salary(
    must_skills: Sequence[str],
    nice_skills: Sequence[str],
    seniority: str,
    location: str,
    job_type: str,
) -> Tuple[float, str]:
    """Estimate expected salary or hourly rate.

    Args:
        must_skills: Must-have skills.
        nice_skills: Nice-to-have skills.
        seniority: Seniority level.
        location: Job location.
        job_type: Type of contract, e.g., "permanent" or "contract".

    Returns:
        Tuple containing the numeric value and mode ("annual" or "hourly").
    """

    seniority_factor = SENIORITY_FACTOR.get(seniority.lower(), 1.0)
    location_factor = LOCATION_FACTOR.get(location.lower(), 1.0)
    if job_type.lower() == "contract":
        base_rate = 40.0
        base_rate += len(must_skills) * 2.0
        base_rate += len(nice_skills) * 1.0
        value = base_rate * seniority_factor * location_factor
        return round(value, 2), "hourly"
    salary = 50000.0
    salary += len(must_skills) * 2000.0
    salary += len(nice_skills) * 1000.0
    value = salary * seniority_factor * location_factor
    return round(value), "annual"


def _session_list(key: str) -> list[str]:
    """Extract a clean list of strings from ``st.session_state``."""

    raw = st.session_state.get(key, "")
    if isinstance(raw, str):
        return [s.strip() for s in raw.splitlines() if s.strip()]
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    return []


def render_salary_dashboard() -> None:
    """Render salary analytics widget in the sidebar."""

    must_skills = _session_list("hard_skills")
    nice_skills = _session_list("soft_skills")
    seniority = st.session_state.get("seniority_level", "")
    location = st.session_state.get("location", "")
    job_type = st.session_state.get("job_type", "permanent")
    job_title = st.session_state.get("job_title", "")

    value, mode = compute_expected_salary(
        must_skills, nice_skills, seniority, location, job_type
    )
    unit = "€/year" if mode == "annual" else "€/hour"

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='text-align:center;font-size:3rem'>💰</div>"  # noqa: E501
        f"<div style='text-align:center;font-size:1.5rem;font-weight:bold'>"
        f"{value:,.2f} {unit}</div>",
        unsafe_allow_html=True,
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
            + "Explain the factors affecting the expected salary in a "
            f"{length} explanation."
        )
        try:
            explanation = call_chat_api(
                [{"role": "user", "content": prompt}], max_tokens=300
            )
            st.sidebar.info(explanation)
        except Exception as exc:  # pragma: no cover - network failure
            st.sidebar.error(str(exc))
