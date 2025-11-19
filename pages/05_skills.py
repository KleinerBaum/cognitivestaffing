from __future__ import annotations

from pages.base import WizardPage


_REQUIRED_FIELDS: tuple[str, ...] = ()
_SUMMARY_FIELDS: tuple[str, ...] = (
    "requirements.hard_skills_required",
    "requirements.soft_skills_required",
    "requirements.hard_skills_optional",
    "requirements.soft_skills_optional",
    "requirements.tools_and_technologies",
    "requirements.languages_required",
    "requirements.languages_optional",
    "requirements.certifications",
)


PAGE = WizardPage(
    key="skills",
    label=("Kompetenzen", "Skills"),
    panel_header=("Skill-Portfolio", "Skill portfolio"),
    panel_subheader=("Pflicht & Optional", "Required & optional"),
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
            "Markiere locker, was die Person wirklich können muss – den Rest packen wir unter Optional.",
            "Flag what this person absolutely needs to know and we’ll park the rest as optional.",
        ),
    ),
    required_fields=_REQUIRED_FIELDS,
    summary_fields=_SUMMARY_FIELDS,
    allow_skip=False,
)
