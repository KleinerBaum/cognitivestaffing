from __future__ import annotations

from constants.keys import ProfilePaths
from core.schema import is_wizard_schema_enabled

from .base import WizardPage


if is_wizard_schema_enabled():
    _REQUIRED_FIELDS = ("skills.must_have",)
    _SUMMARY_FIELDS = (
        "skills.must_have",
        "skills.nice_to_have",
        "skills.certifications",
        "skills.tools",
        "skills.languages",
    )
else:
    _REQUIRED_FIELDS = tuple(
        field.value
        for field in (
            ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED,
            ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED,
        )
    )
    _SUMMARY_FIELDS = tuple(
        field.value
        for field in (
            ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED,
            ProfilePaths.REQUIREMENTS_HARD_SKILLS_OPTIONAL,
            ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED,
            ProfilePaths.REQUIREMENTS_SOFT_SKILLS_OPTIONAL,
            ProfilePaths.REQUIREMENTS_TOOLS_AND_TECHNOLOGIES,
            ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED,
            ProfilePaths.REQUIREMENTS_LANGUAGES_OPTIONAL,
            ProfilePaths.REQUIREMENTS_LANGUAGE_LEVEL_ENGLISH,
            ProfilePaths.REQUIREMENTS_CERTIFICATIONS,
            ProfilePaths.REQUIREMENTS_CERTIFICATES,
        )
    )


PAGE = WizardPage(
    key="skills",
    label=("Kompetenzen", "Skills"),
    panel_header=("Skill-Portfolio", "Skill portfolio"),
    panel_subheader=("Muss & Nice-to-have", "Must & nice-to-have"),
    panel_intro_variants=(
        (
            "Lege fest, welche Kompetenzen zwingend und welche optional sind.",
            "Specify which competencies are mandatory and which are optional.",
        ),
        (
            "Sauber strukturierte Skill-Daten verbessern Scoring, Marktvergleiche und Exportqualität.",
            "Well-structured skill data improves scoring, market benchmarks, and export quality.",
        ),
        (
            "Markiere locker, was die Person wirklich können muss – den Rest packen wir unter Nice-to-have.",
            "Flag what this person absolutely needs to know and we’ll park the rest as nice-to-have.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
