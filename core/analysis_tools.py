"""Domain-specific tools for recruitment need analysis.

This module provides helper functions that the language model can invoke via
the OpenAI ``tools`` interface. The functions are intentionally lightweight and
rely on curated static data so they can run in offline environments and unit
tests.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Final, Mapping, Tuple


# Salary data focuses on core IT and project-management roles that appear most
# frequently in Cognitive Staffing engagements. Ranges were derived from public
# 2024 benchmarks (US national averages, major German hubs) and rounded to keep
# prompts compact while still giving the LLM grounded guardrails.
SALARY_BENCHMARKS: Final[Mapping[str, Mapping[str, str]]] = {
    "software developer": {"US": "$100k-$145k", "DE": "€60k-€85k"},
    "software engineer": {"US": "$105k-$150k", "DE": "€70k-€95k"},
    "backend engineer": {"US": "$110k-$155k", "DE": "€72k-€98k"},
    "frontend engineer": {"US": "$95k-$140k", "DE": "€65k-€90k"},
    "full stack engineer": {"US": "$105k-$155k", "DE": "€70k-€96k"},
    "cloud engineer": {"US": "$115k-$165k", "DE": "€75k-€102k"},
    "devops engineer": {"US": "$115k-$170k", "DE": "€78k-€105k"},
    "data engineer": {"US": "$115k-$170k", "DE": "€76k-€105k"},
    "data scientist": {"US": "$115k-$165k", "DE": "€75k-€100k"},
    "ml engineer": {"US": "$120k-$180k", "DE": "€80k-€110k"},
    "cybersecurity analyst": {"US": "$100k-$145k", "DE": "€68k-€92k"},
    "qa engineer": {"US": "$85k-$120k", "DE": "€58k-€80k"},
    "it project manager": {"US": "$105k-$145k", "DE": "€70k-€95k"},
    "technical project manager": {"US": "$110k-$150k", "DE": "€72k-€98k"},
    "agile project manager": {"US": "$105k-$150k", "DE": "€70k-€95k"},
    "scrum master": {"US": "$95k-$130k", "DE": "€62k-€85k"},
    "product manager": {"US": "$120k-$175k", "DE": "€78k-€108k"},
    "program manager": {"US": "$125k-$185k", "DE": "€82k-€112k"},
    "business analyst": {"US": "$90k-$125k", "DE": "€60k-€82k"},
    "it service manager": {"US": "$95k-$135k", "DE": "€62k-€86k"},
}


# Short, recruitment-relevant definitions help the model ground suggested
# competencies when vetting IT and project-management profiles.
SKILL_DEFINITIONS: Final[Mapping[str, str]] = {
    "project management": "Planning, coordinating, and delivering scoped outcomes on time.",
    "python": "High-level language for data engineering, ML, and automation.",
    "java": "Object-oriented language common in enterprise backends.",
    "c#": "Microsoft-focused language for backend, desktop, and cloud apps.",
    "typescript": "Typed superset of JavaScript used for scalable frontends.",
    "react": "Frontend library for building interactive web interfaces.",
    "sql": "Language for querying and modeling relational databases.",
    "aws": "Amazon cloud platform offering compute, storage, and DevOps tools.",
    "azure": "Microsoft cloud platform for enterprise workloads and data.",
    "gcp": "Google Cloud Platform for analytics, ML, and infrastructure.",
    "docker": "Containerization platform for packaging and shipping software.",
    "kubernetes": "Orchestrates containers for resilient, scalable deployments.",
    "terraform": "Infrastructure-as-code tool for provisioning cloud resources.",
    "devops": "Practices combining development and operations automation.",
    "agile": "Iterative delivery framework focused on rapid customer feedback.",
    "scrum": "Agile framework with time-boxed sprints and defined ceremonies.",
    "kanban": "Flow-based agile method emphasizing work-in-progress limits.",
    "jira": "Atlassian tool for agile backlog, sprint, and issue tracking.",
    "confluence": "Workspace for documenting project decisions and knowledge.",
    "stakeholder management": "Aligning expectations and communication across business groups.",
    "risk management": "Identifying, assessing, and mitigating delivery risks.",
    "budgeting": "Planning and tracking project costs against forecasts.",
    "resource planning": "Allocating team capacity to meet project commitments.",
    "change management": "Guiding organizations through process or system transitions.",
    "quality assurance": "Ensuring deliverables meet acceptance and compliance criteria.",
    "business analysis": "Translating business needs into actionable requirements.",
    "stakeholder communication": "Structuring updates for executives, teams, and clients.",
    "it governance": "Policies ensuring IT aligns with business strategy and compliance.",
}


def get_salary_benchmark(role: str, country: str = "US") -> Dict[str, str]:
    """Return a naive annual salary benchmark for ``role`` in ``country``.

    The values are illustrative only. A production implementation should query
    a dedicated compensation API or database.

    Args:
        role: Job title to look up.
        country: ISO country code.

    Returns:
        Dictionary with key ``salary_range`` describing the estimated salary.
    """

    role_key = role.lower().strip()
    country_key = country.upper().strip()
    salary = SALARY_BENCHMARKS.get(role_key, {}).get(country_key, "unknown")
    return {"salary_range": salary}


def get_skill_definition(skill: str) -> Dict[str, str]:
    """Return a short definition for a given ``skill``.

    Args:
        skill: Name of the skill.

    Returns:
        Dictionary with key ``definition`` holding a description.
    """

    definition = SKILL_DEFINITIONS.get(
        skill.lower().strip(),
        "definition unavailable",
    )
    return {"definition": definition}


def build_analysis_tools() -> Tuple[list[dict], Mapping[str, Callable[..., Any]]]:
    """Return tool specifications and corresponding callables.

    Returns:
        Tuple containing a list of tool spec dictionaries and a mapping from
        tool name to callable.
    """

    tools = [
        {
            "type": "function",
            "name": "get_salary_benchmark",
            "description": "Fetch a rough annual salary range for a role in a country.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["role"],
            },
        },
        {
            "type": "function",
            "name": "get_skill_definition",
            "description": "Return a concise definition for a skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                },
                "required": ["skill"],
            },
        },
    ]
    funcs: Mapping[str, Callable[..., Any]] = {
        "get_salary_benchmark": get_salary_benchmark,
        "get_skill_definition": get_skill_definition,
    }
    return tools, funcs


__all__ = [
    "get_salary_benchmark",
    "get_skill_definition",
    "build_analysis_tools",
]
