"""Domain-specific tools for recruitment need analysis.

This module provides helper functions that the language model can invoke via
the OpenAI ``tools`` interface. The functions are intentionally lightweight and
rely on static data so they can run in offline environments and unit tests.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Tuple


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

    data: Dict[str, Dict[str, str]] = {
        "software developer": {"US": "$90k-$130k", "DE": "€60k-€85k"},
        "data scientist": {"US": "$95k-$140k", "DE": "€65k-€90k"},
    }
    role_key = role.lower().strip()
    country_key = country.upper().strip()
    salary = data.get(role_key, {}).get(country_key, "unknown")
    return {"salary_range": salary}


def get_skill_definition(skill: str) -> Dict[str, str]:
    """Return a short definition for a given ``skill``.

    Args:
        skill: Name of the skill.

    Returns:
        Dictionary with key ``definition`` holding a description.
    """

    definitions: Dict[str, str] = {
        "python": "A high-level programming language known for readability.",
        "project management": "Planning and overseeing projects to meet goals.",
    }
    definition = definitions.get(skill.lower().strip(), "definition unavailable")
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
