"""Utilities for job advertisement configuration and targeting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from models.need_analysis import NeedAnalysisProfile


@dataclass(frozen=True)
class JobAdFieldDefinition:
    """Configuration for a single field that can be published in the job ad."""

    key: str
    group: str
    label_de: str
    label_en: str
    description_de: str | None = None
    description_en: str | None = None


# Order aligns with wizard steps for intuitive selection in the UI.
JOB_AD_FIELDS: Sequence[JobAdFieldDefinition] = (
    JobAdFieldDefinition(
        "position.job_title",
        "basic",
        "Jobtitel",
        "Job Title",
        "Titel der ausgeschriebenen Position",
        "Title of the open position",
    ),
    JobAdFieldDefinition(
        "position.seniority_level",
        "basic",
        "Erfahrungsebene",
        "Seniority Level",
    ),
    JobAdFieldDefinition(
        "company.name",
        "company",
        "Unternehmen",
        "Company",
    ),
    JobAdFieldDefinition(
        "company.brand_name",
        "company",
        "Markenname",
        "Brand Name",
    ),
    JobAdFieldDefinition(
        "company.size",
        "company",
        "Unternehmensgröße",
        "Company Size",
    ),
    JobAdFieldDefinition(
        "company.industry",
        "company",
        "Branche",
        "Industry",
    ),
    JobAdFieldDefinition(
        "company.mission",
        "company",
        "Mission",
        "Mission",
    ),
    JobAdFieldDefinition(
        "company.culture",
        "company",
        "Kultur",
        "Culture",
    ),
    JobAdFieldDefinition(
        "location.primary_city",
        "basic",
        "Standort",
        "Location",
    ),
    JobAdFieldDefinition(
        "location.country",
        "basic",
        "Land",
        "Country",
    ),
    JobAdFieldDefinition(
        "position.role_summary",
        "basic",
        "Rollenübersicht",
        "Role Summary",
    ),
    JobAdFieldDefinition(
        "position.key_projects",
        "basic",
        "Schlüsselprojekte",
        "Key Projects",
    ),
    JobAdFieldDefinition(
        "position.team_structure",
        "basic",
        "Teamstruktur",
        "Team Structure",
    ),
    JobAdFieldDefinition(
        "position.team_size",
        "basic",
        "Teamgröße",
        "Team Size",
    ),
    JobAdFieldDefinition(
        "position.reporting_line",
        "basic",
        "Berichtsweg",
        "Reporting Line",
    ),
    JobAdFieldDefinition(
        "responsibilities.items",
        "requirements",
        "Aufgaben",
        "Key Responsibilities",
    ),
    JobAdFieldDefinition(
        "requirements.hard_skills_required",
        "requirements",
        "Hard Skills (Muss)",
        "Hard Skills (Must-have)",
    ),
    JobAdFieldDefinition(
        "requirements.hard_skills_optional",
        "requirements",
        "Hard Skills (Optional)",
        "Hard Skills (Nice-to-have)",
    ),
    JobAdFieldDefinition(
        "requirements.soft_skills_required",
        "requirements",
        "Soft Skills (Muss)",
        "Soft Skills (Must-have)",
    ),
    JobAdFieldDefinition(
        "requirements.soft_skills_optional",
        "requirements",
        "Soft Skills (Optional)",
        "Soft Skills (Nice-to-have)",
    ),
    JobAdFieldDefinition(
        "requirements.tools_and_technologies",
        "requirements",
        "Tools & Technologien",
        "Tools & Technologies",
    ),
    JobAdFieldDefinition(
        "requirements.languages_required",
        "requirements",
        "Erforderliche Sprachen",
        "Languages Required",
    ),
    JobAdFieldDefinition(
        "requirements.background_check_required",
        "requirements",
        "Hintergrundprüfung erforderlich",
        "Background Check Required",
        "Zeigt an, ob Bewerber:innen eine Sicherheits-/Compliance-Prüfung bestehen müssen.",
        "Indicates whether candidates must pass a security/compliance background screening.",
    ),
    JobAdFieldDefinition(
        "requirements.reference_check_required",
        "requirements",
        "Referenzprüfung erforderlich",
        "Reference Check Required",
        "Markiert, ob Referenzgespräche verpflichtend eingeholt werden.",
        "Highlights that reference calls are mandatory before hiring decisions.",
    ),
    JobAdFieldDefinition(
        "requirements.portfolio_required",
        "requirements",
        "Portfolio erforderlich",
        "Portfolio Required",
        "Definiert, ob Bewerbungen nur mit Arbeitsproben/Portfolio berücksichtigt werden.",
        "Specifies whether applications must include work samples or a portfolio.",
    ),
    JobAdFieldDefinition(
        "employment.job_type",
        "employment",
        "Anstellungsart",
        "Job Type",
    ),
    JobAdFieldDefinition(
        "employment.contract_type",
        "employment",
        "Vertragsart",
        "Contract Type",
    ),
    JobAdFieldDefinition(
        "employment.work_policy",
        "employment",
        "Arbeitsmodell",
        "Work Policy",
    ),
    JobAdFieldDefinition(
        "employment.work_schedule",
        "employment",
        "Arbeitszeit",
        "Work Schedule",
    ),
    JobAdFieldDefinition(
        "employment.remote_percentage",
        "employment",
        "Remote-Anteil",
        "Remote Percentage",
    ),
    JobAdFieldDefinition(
        "employment.travel_required",
        "employment",
        "Reisebereitschaft",
        "Travel Requirements",
    ),
    JobAdFieldDefinition(
        "employment.travel_details",
        "employment",
        "Details zur Reisebereitschaft",
        "Travel Details",
    ),
    JobAdFieldDefinition(
        "employment.relocation_support",
        "employment",
        "Umzugsunterstützung",
        "Relocation Support",
    ),
    JobAdFieldDefinition(
        "employment.relocation_details",
        "employment",
        "Details zur Umzugsunterstützung",
        "Relocation Details",
    ),
    JobAdFieldDefinition(
        "employment.visa_sponsorship",
        "employment",
        "Visa-Sponsoring",
        "Visa Sponsorship",
    ),
    JobAdFieldDefinition(
        "compensation.salary",
        "compensation",
        "Gehaltsspanne",
        "Salary Range",
    ),
    JobAdFieldDefinition(
        "compensation.benefits",
        "compensation",
        "Benefits",
        "Benefits",
    ),
    JobAdFieldDefinition(
        "compensation.learning_budget",
        "compensation",
        "Weiterbildungsbudget",
        "Learning Budget",
    ),
    JobAdFieldDefinition(
        "process.application_instructions",
        "process",
        "Bewerbungshinweise",
        "Application Instructions",
    ),
    JobAdFieldDefinition(
        "meta.application_deadline",
        "process",
        "Bewerbungsschluss",
        "Application Deadline",
    ),
)


def resolve_job_ad_field_selection(
    available_keys: Iterable[str],
    selected_keys: Iterable[str] | None = None,
) -> list[str]:
    """Return ordered job-ad field keys that should be included in the payload.

    The helper keeps the canonical ``JOB_AD_FIELDS`` ordering while ensuring that
    only field keys present in ``available_keys`` survive. ``selected_keys`` may
    contain arbitrary values (e.g., from persisted session state); keys without
    captured values are discarded.
    """

    available_set = {key for key in available_keys}
    if selected_keys is None:
        selected_set = available_set
    else:
        selected_set = {key for key in selected_keys if key in available_set}
    return [field.key for field in JOB_AD_FIELDS if field.key in selected_set]


JOB_AD_GROUP_LABELS = {
    "company": ("Unternehmen", "Company"),
    "basic": ("Basisdaten", "Basic information"),
    "requirements": ("Anforderungen", "Requirements"),
    "employment": ("Beschäftigung", "Employment"),
    "compensation": ("Vergütung", "Compensation"),
    "process": ("Prozess", "Process"),
}


@dataclass(frozen=True)
class TargetAudienceSuggestion:
    """Describes a suggested audience focus for the job advertisement."""

    key: str
    title: str
    description: str


def suggest_target_audiences(
    profile: NeedAnalysisProfile,
    lang: str,
) -> Sequence[TargetAudienceSuggestion]:
    """Return heuristic target audience suggestions based on profile data."""

    lang = (lang or "de").lower()
    is_de = lang.startswith("de")

    job_title = profile.position.job_title or profile.department.name or ""
    seniority = (profile.position.seniority_level or "").lower()
    work_policy = (profile.employment.work_policy or "").lower()
    remote_percentage = profile.employment.remote_percentage or 0
    location = profile.location.primary_city or profile.location.country or ""
    benefits = profile.compensation.benefits
    culture = profile.company.culture or ""

    audience: list[TargetAudienceSuggestion] = []

    if "senior" in seniority or "lead" in seniority or "principal" in seniority:
        title_de = "Erfahrene Führungskräfte"
        title_en = "Seasoned Leaders"
        description_de = (
            f"Ansprache von Senior-Talenten für {job_title} mit Fokus auf strategische Wirkung"
            if job_title
            else "Ansprache von Senior-Talenten mit strategischem Fokus"
        )
        description_en = (
            f"Engage senior professionals for the {job_title} role with a strategic impact"
            if job_title
            else "Engage senior professionals with a strategic focus"
        )
    else:
        title_de = "Ambitionierte Fachkräfte"
        title_en = "Ambitious Professionals"
        description_de = (
            f"Betont Entwicklungschancen und Mentoring für {job_title}" if job_title else "Betont Entwicklungschancen"
        )
        description_en = (
            f"Highlights growth opportunities and mentoring for {job_title}"
            if job_title
            else "Highlights growth opportunities"
        )
    audience.append(
        TargetAudienceSuggestion(
            "experience",
            title_de if is_de else title_en,
            description_de if is_de else description_en,
        )
    )

    if work_policy in {"remote", "hybrid"} or remote_percentage >= 50:
        title_de = "Remote-orientierte Spezialist:innen"
        title_en = "Remote-first Specialists"
        location_note_de = f" mit Standortbezug {location}" if location else ""
        location_note_en = f" while referencing {location}" if location else ""
        description_de = (
            "Fokussiert flexible Arbeitsmodelle, digitale Zusammenarbeit und klare Kommunikationswege"
            + location_note_de
        )
        description_en = (
            "Focuses on flexible work setups, digital collaboration and clear communication routines" + location_note_en
        )
        key = "remote"
    else:
        title_de = "Regionale Talente"
        title_en = "Local Talent"
        location_phrase_de = f" im Raum {location}" if location else ""
        location_phrase_en = f" around {location}" if location else ""
        description_de = "Betont die Präsenzkultur, kurze Entscheidungswege und Teamzusammenhalt" + location_phrase_de
        description_en = "Highlights on-site collaboration, quick decisions and close-knit teams" + location_phrase_en
        key = "local"
    audience.append(
        TargetAudienceSuggestion(
            key,
            title_de if is_de else title_en,
            description_de if is_de else description_en,
        )
    )

    if benefits or culture:
        title_de = "Kultur- und Benefit-orientierte Kandidat:innen"
        title_en = "Culture & Benefits Driven Candidates"
        if benefits:
            perks = ", ".join(benefits[:3])
            desc_de = f"Stellt Benefits wie {perks} und gelebte Werte in den Mittelpunkt"
            desc_en = f"Puts benefits such as {perks} and company values at the centre"
        elif culture:
            desc_de = f"Hervorhebung der Unternehmenskultur: {culture}"
            desc_en = f"Highlight the company culture: {culture}"
        else:
            desc_de = "Hebt Benefits und Kultur hervor"
            desc_en = "Highlights benefits and company culture"
    else:
        title_de = "Wachstumsorientierte Talente"
        title_en = "Growth-minded Talent"
        desc_de = "Betont Lernpfade, Onboarding und Weiterentwicklung"
        desc_en = "Emphasises learning paths, onboarding and development"
    audience.append(
        TargetAudienceSuggestion(
            "culture",
            title_de if is_de else title_en,
            desc_de if is_de else desc_en,
        )
    )

    return audience


def iter_field_keys(keys: Iterable[str]) -> Sequence[str]:
    """Return a tuple of known field keys, filtering unknown entries."""

    known = {field.key for field in JOB_AD_FIELDS}
    return tuple(key for key in keys if key in known)


__all__ = [
    "JobAdFieldDefinition",
    "JOB_AD_FIELDS",
    "JOB_AD_GROUP_LABELS",
    "TargetAudienceSuggestion",
    "suggest_target_audiences",
    "iter_field_keys",
]
