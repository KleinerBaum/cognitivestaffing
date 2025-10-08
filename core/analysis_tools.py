"""Domain-specific tools for recruitment need analysis.

This module provides helper functions that the language model can invoke via
the OpenAI ``tools`` interface. The functions are intentionally lightweight and
rely on curated static data so they can run in offline environments and unit
tests.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Callable, Dict, Final, Mapping, Sequence, Tuple, TypedDict

from config_loader import load_json


class _SalaryBenchmarkEntry(TypedDict, total=False):
    """Serialized salary benchmark entry loaded from configuration."""

    aliases: Sequence[str]
    keywords: Sequence[str]
    ranges: Mapping[str, str]


def _normalize_token(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_only.lower().split())


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


# Salary data focuses on core IT and project-management roles that appear most
# frequently in Cognitive Staffing engagements. Ranges were derived from public
# 2024 benchmarks (US national averages, major German hubs) and rounded to keep
# prompts compact while still giving the LLM grounded guardrails.
_DEFAULT_SALARY_DATA: Final[dict[str, _SalaryBenchmarkEntry]] = {
    "software developer": {
        "aliases": [
            "software developer",
            "softwareentwickler",
            "software entwickler",
            "software-entwickler",
        ],
        "keywords": ["software", "entwickler"],
        "ranges": {"US": "$100k-$145k", "DE": "€60k-€85k"},
    },
    "software engineer": {
        "aliases": ["software engineer", "software ingenieur"],
        "keywords": ["software", "engineer"],
        "ranges": {"US": "$105k-$150k", "DE": "€70k-€95k"},
    },
    "backend engineer": {
        "aliases": ["backend engineer", "backend entwickler"],
        "keywords": ["backend"],
        "ranges": {"US": "$110k-$155k", "DE": "€72k-€98k"},
    },
    "frontend engineer": {
        "aliases": ["frontend engineer", "frontend entwickler", "frontend developer"],
        "keywords": ["frontend"],
        "ranges": {"US": "$95k-$140k", "DE": "€65k-€90k"},
    },
    "full stack engineer": {
        "aliases": [
            "full stack engineer",
            "fullstack engineer",
            "fullstack entwickler",
        ],
        "keywords": ["full", "stack"],
        "ranges": {"US": "$105k-$155k", "DE": "€70k-€96k"},
    },
    "cloud engineer": {
        "aliases": ["cloud engineer", "cloud spezialist"],
        "keywords": ["cloud"],
        "ranges": {"US": "$115k-$165k", "DE": "€75k-€102k"},
    },
    "devops engineer": {
        "aliases": ["devops engineer", "devops spezialist"],
        "keywords": ["devops"],
        "ranges": {"US": "$115k-$170k", "DE": "€78k-€105k"},
    },
    "data engineer": {
        "aliases": ["data engineer", "dateningenieur"],
        "keywords": ["data", "engineer"],
        "ranges": {"US": "$115k-$170k", "DE": "€76k-€105k"},
    },
    "data scientist": {
        "aliases": ["data scientist", "datenwissenschaftler"],
        "keywords": ["data", "scientist"],
        "ranges": {"US": "$115k-$165k", "DE": "€75k-€100k"},
    },
    "ml engineer": {
        "aliases": ["ml engineer", "machine learning engineer"],
        "keywords": ["machine", "learning"],
        "ranges": {"US": "$120k-$180k", "DE": "€80k-€110k"},
    },
    "cybersecurity analyst": {
        "aliases": ["cybersecurity analyst", "it sicherheitsanalyst"],
        "keywords": ["security"],
        "ranges": {"US": "$100k-$145k", "DE": "€68k-€92k"},
    },
    "qa engineer": {
        "aliases": ["qa engineer", "qa tester", "qualitaetssicherung"],
        "keywords": ["qa"],
        "ranges": {"US": "$85k-$120k", "DE": "€58k-€80k"},
    },
    "it project manager": {
        "aliases": ["it project manager", "it projektleiter"],
        "keywords": ["projektleiter"],
        "ranges": {"US": "$105k-$145k", "DE": "€70k-€95k"},
    },
    "technical project manager": {
        "aliases": [
            "technical project manager",
            "technischer projektleiter",
        ],
        "keywords": ["technisch", "projekt"],
        "ranges": {"US": "$110k-$150k", "DE": "€72k-€98k"},
    },
    "agile project manager": {
        "aliases": ["agile project manager", "agiler projektmanager"],
        "keywords": ["agile", "projekt"],
        "ranges": {"US": "$105k-$150k", "DE": "€70k-€95k"},
    },
    "scrum master": {
        "aliases": ["scrum master", "scrum-master"],
        "keywords": ["scrum"],
        "ranges": {"US": "$95k-$130k", "DE": "€62k-€85k"},
    },
    "product manager": {
        "aliases": [
            "product manager",
            "produktmanager",
            "produkt manager",
        ],
        "keywords": ["product", "manager"],
        "ranges": {"US": "$120k-$175k", "DE": "€78k-€108k"},
    },
    "program manager": {
        "aliases": ["program manager", "programm manager", "programmleiter"],
        "keywords": ["program", "manager"],
        "ranges": {"US": "$125k-$185k", "DE": "€82k-€112k"},
    },
    "business analyst": {
        "aliases": [
            "business analyst",
            "business-analyst",
            "business analyse",
        ],
        "keywords": ["business", "analyst"],
        "ranges": {"US": "$90k-$125k", "DE": "€60k-€82k"},
    },
    "it service manager": {
        "aliases": ["it service manager", "it serviceleiter"],
        "keywords": ["service", "manager"],
        "ranges": {"US": "$95k-$135k", "DE": "€62k-€86k"},
    },
    "product owner": {
        "aliases": ["product owner", "produkt owner", "product-owner"],
        "keywords": ["product", "owner"],
        "ranges": {"US": "$105k-$145k", "DE": "€70k-€95k"},
    },
    "product developer": {
        "aliases": [
            "product developer",
            "produktentwickler",
            "produktentwicklung",
        ],
        "keywords": ["produktentwickler"],
        "ranges": {"US": "$95k-$135k", "DE": "€65k-€90k"},
    },
    "data analyst": {
        "aliases": ["data analyst", "datenanalyst", "data-analyst"],
        "keywords": ["data", "analyst"],
        "ranges": {"US": "$75k-$110k", "DE": "€55k-€78k"},
    },
    "solution architect": {
        "aliases": ["solution architect", "solutionsarchitekt", "loesungsarchitekt"],
        "keywords": ["solution", "architect"],
        "ranges": {"US": "$130k-$185k", "DE": "€85k-€115k"},
    },
    "mobile engineer": {
        "aliases": ["mobile engineer", "mobile entwickler", "app entwickler"],
        "keywords": ["mobile"],
        "ranges": {"US": "$105k-$150k", "DE": "€68k-€95k"},
    },
}


def _load_salary_data() -> dict[str, _SalaryBenchmarkEntry]:
    raw_data = load_json("salary_benchmarks.json", fallback=_DEFAULT_SALARY_DATA)
    if not isinstance(raw_data, Mapping):
        return dict(_DEFAULT_SALARY_DATA)
    prepared: dict[str, _SalaryBenchmarkEntry] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        aliases = _as_list(value.get("aliases", []))
        keywords = _as_list(value.get("keywords", []))
        ranges_value = value.get("ranges", {})
        ranges: dict[str, str] = {}
        if isinstance(ranges_value, Mapping):
            for country_key, salary_range in ranges_value.items():
                if not isinstance(country_key, str) or not isinstance(salary_range, str):
                    continue
                cleaned_country = country_key.strip().upper()
                cleaned_range = salary_range.strip()
                if cleaned_country and cleaned_range:
                    ranges[cleaned_country] = cleaned_range
        if not ranges:
            continue
        prepared[key.strip().lower()] = {
            "aliases": aliases,
            "keywords": keywords,
            "ranges": ranges,
        }
    return prepared or dict(_DEFAULT_SALARY_DATA)


_SALARY_DATA: Final[dict[str, _SalaryBenchmarkEntry]] = _load_salary_data()
SALARY_BENCHMARKS: Final[Mapping[str, Mapping[str, str]]] = {
    role: entry["ranges"] for role, entry in _SALARY_DATA.items()
}

_ROLE_INDEX: dict[str, str] = {}
_ROLE_FRAGMENTS: list[tuple[str, str]] = []
_ROLE_KEYWORDS: dict[str, list[str]] = {}
for canonical_role, entry in _SALARY_DATA.items():
    normalized_role = _normalize_token(canonical_role)
    _ROLE_INDEX[normalized_role] = canonical_role
    _ROLE_KEYWORDS[canonical_role] = [
        _normalize_token(keyword) for keyword in entry.get("keywords", []) if keyword
    ]
    _ROLE_FRAGMENTS.append((normalized_role, canonical_role))
    for alias in entry.get("aliases", []):
        normalized_alias = _normalize_token(alias)
        if not normalized_alias:
            continue
        _ROLE_INDEX.setdefault(normalized_alias, canonical_role)
        _ROLE_FRAGMENTS.append((normalized_alias, canonical_role))

_ROLE_FRAGMENTS.sort(key=lambda item: len(item[0]), reverse=True)


def resolve_salary_role(role: str) -> str | None:
    """Return the canonical salary role key for ``role`` if available."""

    normalized_input = _normalize_token(role)
    if not normalized_input:
        return None

    direct = _ROLE_INDEX.get(normalized_input)
    if direct:
        return direct

    for fragment, canonical in _ROLE_FRAGMENTS:
        if fragment and fragment in normalized_input:
            return canonical

    for canonical, keywords in _ROLE_KEYWORDS.items():
        if keywords and all(keyword in normalized_input for keyword in keywords):
            return canonical

    return None


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

    canonical_role = resolve_salary_role(role) or _normalize_token(role)
    role_key = canonical_role.lower().strip()
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
    "resolve_salary_role",
    "get_skill_definition",
    "build_analysis_tools",
]
