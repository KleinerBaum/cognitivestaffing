"""Predefined suggestion lists for common profile fields."""

from typing import Dict, List

from .esco_utils import normalize_skills

FIELD_SUGGESTIONS: Dict[str, List[str]] = {
    "programming_languages": [
        "Python",
        "Java",
        "JavaScript",
        "C#",
        "C++",
        "Go",
        "Ruby",
        "Rust",
    ],
    "frameworks": [
        "Django",
        "Flask",
        "FastAPI",
        "React",
        "Angular",
        "Vue.js",
        "Spring",
        "Laravel",
        "Express.js",
    ],
    "databases": [
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "SQLite",
        "Redis",
        "Oracle",
        "SQL Server",
        "Elasticsearch",
    ],
    "cloud_providers": [
        "AWS",
        "Azure",
        "Google Cloud Platform",
        "Heroku",
        "DigitalOcean",
    ],
    "devops_tools": [
        "Docker",
        "Kubernetes",
        "Terraform",
        "Ansible",
        "Jenkins",
        "GitLab CI",
        "GitHub Actions",
    ],
}

__all__ = ["FIELD_SUGGESTIONS", "get_field_suggestions"]


def get_field_suggestions(field: str, lang: str = "en") -> List[str]:
    """Return normalized suggestions for a profile field.

    Args:
        field: Field name such as ``"programming_languages"``.
        lang: Target language code for normalization.

    Returns:
        A list of suggestions with consistent formatting.
    """

    skills = FIELD_SUGGESTIONS.get(field, [])
    return normalize_skills(skills, lang=lang)
