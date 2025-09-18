"""Sidebar salary analytics dashboard component."""

from datetime import datetime
from typing import Any, Final, Sequence, Tuple

import streamlit as st
from config import ModelTask, get_model_for
from constants.keys import UIKeys
from utils.i18n import tr


# ``openai_utils`` is an optional dependency. Import lazily so that the
# dashboard still renders even if the OpenAI helper is unavailable (e.g.,
# during tests without the SDK installed).
def _call_chat_api(messages: list[dict], **kwargs: Any) -> str:
    """Lazy import wrapper around ``openai_utils.call_chat_api``."""
    from openai_utils import call_chat_api

    if "model" not in kwargs:
        kwargs["model"] = get_model_for(ModelTask.DEFAULT)
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


def _collect_profile_snapshot(session_state: Any) -> dict[str, Any]:
    """Collect profile attributes that influence the salary estimate."""

    must_skills = _session_list(
        session_state, "requirements.hard_skills_required"
    ) + _session_list(session_state, "requirements.soft_skills_required")
    nice_skills = _session_list(
        session_state, "requirements.hard_skills_optional"
    ) + _session_list(session_state, "requirements.soft_skills_optional")
    tasks = _session_list(session_state, "responsibilities.items")
    languages = _session_list(
        session_state, "requirements.languages_required"
    ) + _session_list(session_state, "requirements.languages_optional")

    snapshot = {
        "must_skills": must_skills,
        "nice_skills": nice_skills,
        "seniority": session_state.get("position.seniority_level", ""),
        "location": session_state.get("location.primary_city", ""),
        "job_type": session_state.get("employment.job_type", "permanent"),
        "job_title": session_state.get("position.job_title", ""),
        "tasks": tasks,
        "languages": languages,
        "company_industry": session_state.get("company.industry", ""),
    }
    return snapshot


def _ensure_salary_style() -> None:
    """Inject one-off CSS for the salary insight section."""

    if st.session_state.get("ui.salary.style_injected"):
        return
    st.session_state["ui.salary.style_injected"] = True
    st.markdown(
        """
        <style>
        .salary-card {
            background: linear-gradient(145deg, rgba(79,70,229,0.08), rgba(236,72,153,0.08));
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 1rem;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 14px 38px rgba(15, 23, 42, 0.08);
        }
        .salary-card h4 {
            margin-top: 0;
            margin-bottom: 0.8rem;
            font-size: 1.05rem;
            letter-spacing: 0.01em;
        }
        .salary-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .salary-unit {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-left: 0.35rem;
        }
        .salary-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.25rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            background: rgba(15,23,42,0.05);
            margin: 0 0.35rem 0.35rem 0;
        }
        .salary-explanation {
            background: rgba(15,23,42,0.04);
            border-radius: 0.8rem;
            padding: 0.75rem 0.9rem;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _update_salary_estimate(
    session_state: Any, snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Compute and persist the salary estimate for the current profile."""

    value, mode = compute_expected_salary(
        snapshot["must_skills"],
        snapshot["nice_skills"],
        snapshot["seniority"],
        snapshot["location"],
        snapshot["job_type"],
        snapshot["job_title"],
        snapshot["tasks"],
        snapshot["languages"],
        snapshot["company_industry"],
    )
    lang = session_state.get("lang", "de")
    timestamp = datetime.now()
    last_updated = (
        timestamp.strftime("%d.%m.%Y %H:%M")
        if lang == "de"
        else timestamp.strftime("%Y-%m-%d %H:%M")
    )
    estimate = {
        "value": value,
        "mode": mode,
        "snapshot": snapshot,
        "last_updated": last_updated,
    }
    session_state[UIKeys.SALARY_ESTIMATE] = estimate
    return estimate


def _format_currency(value: float, mode: str, lang: str) -> str:
    """Format numeric salary value according to the current language."""

    if mode == "annual":
        pattern = "{value:,.0f}"
    else:
        pattern = "{value:,.2f}"
    formatted = pattern.format(value=value)
    if lang == "de":
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def _render_context_pills(snapshot: dict[str, Any]) -> str:
    """Render HTML pills summarising input drivers."""

    pills: list[str] = []
    if snapshot["job_title"]:
        pills.append(f"<span class='salary-pill'>🧑‍💼 {snapshot['job_title']}</span>")
    if snapshot["seniority"]:
        pills.append(f"<span class='salary-pill'>🎯 {snapshot['seniority']}</span>")
    if snapshot["location"]:
        pills.append(f"<span class='salary-pill'>📍 {snapshot['location']}</span>")
    pills.append(
        f"<span class='salary-pill'>🛠️ {len(snapshot['must_skills']) + len(snapshot['nice_skills'])} Skills</span>"
    )
    pills.append(f"<span class='salary-pill'>🗒️ {len(snapshot['tasks'])} Tasks</span>")
    if snapshot["languages"]:
        pills.append(
            f"<span class='salary-pill'>🗣️ {len(snapshot['languages'])} Languages</span>"
        )
    return "".join(pills)


def render_salary_insights(session_state: Any) -> None:
    """Render the salary insight card within wizard steps.

    Args:
        session_state: Streamlit session state used to fetch profile data.
    """

    _ensure_salary_style()
    snapshot = _collect_profile_snapshot(session_state)

    estimate: dict[str, Any] = session_state.get(UIKeys.SALARY_ESTIMATE, {})
    if not estimate:
        estimate = _update_salary_estimate(session_state, snapshot)

    lang = session_state.get("lang", "de")
    refresh_label = tr("🔄 Prognose aktualisieren", "🔄 Refresh estimate")
    explain_label = tr(
        "🧠 Einflussfaktoren analysieren",
        "🧠 Explain salary drivers",
    )
    section_title = tr("💰 Gehaltsprognose", "💰 Salary outlook")
    unit = (
        tr("€/Jahr", "€/year")
        if estimate.get("mode") == "annual"
        else tr("€/Stunde", "€/hour")
    )

    if st.button(refresh_label, key=UIKeys.SALARY_REFRESH, use_container_width=True):
        estimate = _update_salary_estimate(session_state, snapshot)
        st.toast(tr("Gehaltsprognose aktualisiert", "Salary estimate refreshed"))

    estimate_snapshot = estimate.get("snapshot", snapshot)
    if snapshot != estimate_snapshot:
        st.caption(
            tr(
                "Neue Angaben erkannt – aktualisiere die Prognose, um sie zu berücksichtigen.",
                "New inputs detected – refresh the estimate to include them.",
            )
        )

    formatted_value = _format_currency(
        estimate.get("value", 0.0),
        estimate.get("mode", "annual"),
        lang,
    )
    pills_html = _render_context_pills(estimate_snapshot)

    st.markdown(
        f"<div class='salary-card'><h4>{section_title}</h4>"
        f"<div class='salary-value'>{formatted_value}<span class='salary-unit'>{unit}</span></div>"
        f"<div>{pills_html}</div>"
        f"<div style='margin-top:0.75rem;font-size:0.85rem;opacity:0.7;'>"
        + tr(
            "Basis: aktuelle Angaben zu Rolle, Standort, Skills und Aufgaben.",
            "Based on the current role, location, skill and task inputs.",
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )

    if estimate.get("last_updated"):
        st.caption(
            tr(
                f"Zuletzt aktualisiert um {estimate['last_updated']}",
                f"Last refreshed at {estimate['last_updated']}",
            )
        )

    explain_clicked = st.button(
        explain_label,
        key=UIKeys.SALARY_EXPLANATION_BUTTON,
        use_container_width=True,
    )

    explanation_state: str = session_state.get(UIKeys.SALARY_EXPLANATION, "")

    if explain_clicked:
        prompt_lang = "German" if lang == "de" else "English"
        prompt = (
            "You are an experienced compensation analyst."
            " Analyse the biggest positive and negative drivers for the following salary estimate and"
            " suggest concrete cost-saving alternatives."
            f" Respond in {prompt_lang}."
            "\n---\n"
            f"Current salary estimate: {formatted_value} {unit}\n"
            f"Contract type: {estimate_snapshot['job_type'] or 'n/a'}\n"
            f"Job title: {estimate_snapshot['job_title'] or 'n/a'}\n"
            f"Seniority: {estimate_snapshot['seniority'] or 'n/a'}\n"
            f"Location: {estimate_snapshot['location'] or 'n/a'}\n"
            f"Industry: {estimate_snapshot['company_industry'] or 'n/a'}\n"
            f"Must-have skills: {', '.join(estimate_snapshot['must_skills']) or 'none'}\n"
            f"Nice-to-have skills: {', '.join(estimate_snapshot['nice_skills']) or 'none'}\n"
            f"Key responsibilities: {', '.join(estimate_snapshot['tasks']) or 'none'}\n"
            f"Languages: {', '.join(estimate_snapshot['languages']) or 'none'}\n"
            "Structure the answer with a short intro, a bullet list of the top 3 cost drivers"
            " and a bullet list with at least 3 pragmatic, cost-saving alternatives."
        )
        try:
            explanation_state = _call_chat_api(
                [{"role": "user", "content": prompt}],
                max_tokens=350,
            )
            session_state[UIKeys.SALARY_EXPLANATION] = explanation_state
        except Exception as exc:  # pragma: no cover - network failure
            st.error(str(exc))
            explanation_state = ""

    if explanation_state:
        st.markdown(
            f"<div class='salary-explanation'>{explanation_state}</div>",
            unsafe_allow_html=True,
        )
