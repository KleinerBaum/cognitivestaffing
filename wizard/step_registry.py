"""Registry for wizard steps, metadata, and canonical order."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from wizard.navigation_types import StepNextResolver, WizardContext

StepPredicate = Callable[[Mapping[str, object], Mapping[str, object]], bool]
StepRenderer = Callable[[WizardContext], None]


@dataclass(frozen=True)
class StepDefinition:
    """Metadata + rendering contract for an individual wizard step. GREP:STEP_META_V2"""

    key: str
    label: tuple[str, str]
    panel_header: tuple[str, str]
    panel_subheader: tuple[str, str]
    panel_intro_variants: tuple[tuple[str, str], ...]
    required_fields: tuple[str, ...]
    summary_fields: tuple[str, ...]
    allow_skip: bool
    renderer: StepRenderer
    next_step_id: StepNextResolver | None = None
    is_active: StepPredicate | None = None


def _schema_has_section(session_state: Mapping[str, object], section: str) -> bool:
    schema = session_state.get("_schema")
    if not isinstance(schema, Mapping):
        return True
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return True
    return section in properties


def _team_step_active(profile: Mapping[str, object], session_state: Mapping[str, object]) -> bool:
    if not _schema_has_section(session_state, "team"):
        return False
    position = profile.get("position") if isinstance(profile, Mapping) else {}
    if isinstance(position, Mapping):
        supervises = position.get("supervises")
        if isinstance(supervises, (int, float)) and supervises <= 0:
            return False
    return True


def _jobad_next_step_id(_context: WizardContext, _session_state: Mapping[str, object]) -> str | None:
    return "company"


def _render_jobad_step(context: WizardContext) -> None:
    from wizard.steps import jobad_step

    jobad_step.step_jobad(context)


def _render_company_step(context: WizardContext) -> None:
    from wizard.steps import company_step

    company_step.step_company(context)


COMPANY_SUMMARY_FIELDS: Final[tuple[str, ...]] = (
    "business_context.domain",
    "business_context.industry_codes",
    "company.name",
    "company.industry",
    "company.size",
    "company.hq_location",
    "company.website",
    "company.mission",
    "company.culture",
    "company.contact_email",
    "company.contact_phone",
    "location.primary_city",
    "location.country",
)


def _render_team_step(context: WizardContext) -> None:
    from wizard.steps import team_step

    team_step.step_team(context)


def _render_role_tasks_step(context: WizardContext) -> None:
    from wizard import flow as wizard_flow

    _ = context
    wizard_flow._step_requirements()


def _render_skills_step(context: WizardContext) -> None:
    from wizard import flow as wizard_flow

    _ = context
    wizard_flow._render_skills_review_step()


def _render_benefits_step(context: WizardContext) -> None:
    from wizard import flow as wizard_flow

    _ = context
    wizard_flow._step_compensation()


def _render_interview_step(context: WizardContext) -> None:
    from wizard import flow as wizard_flow

    _ = context
    wizard_flow._step_process()


def _render_summary_step(context: WizardContext) -> None:
    from wizard import flow as wizard_flow

    wizard_flow._step_summary(dict(context.schema), list(context.critical_fields))


WIZARD_STEPS: Final[tuple[StepDefinition, ...]] = (  # GREP:STEP_REGISTRY_V2
    StepDefinition(
        key="jobad",
        label=("Onboarding", "Onboarding"),
        panel_header=("Onboarding", "Onboarding"),
        panel_subheader=("Quelle & Import", "Source & intake"),
        panel_intro_variants=(
            (
                "Nutze Upload, URL oder Textfeld, um die Stelle zu initialisieren.",
                "Use upload, URL, or manual text to seed the wizard.",
            ),
            (
                "Alle Inhalte lassen sich anschließend verfeinern.",
                "You can refine all extracted details afterwards.",
            ),
        ),
        required_fields=(),
        summary_fields=(),
        allow_skip=False,
        renderer=_render_jobad_step,
        next_step_id=_jobad_next_step_id,
    ),
    StepDefinition(
        key="company",
        label=("Unternehmensdetails", "Company details"),
        panel_header=("Unternehmensdetails", "Company details"),
        panel_subheader=("Profil, Standort & Kontakte", "Profile, location & contacts"),
        panel_intro_variants=(
            (
                "Bitte überprüfe die Unternehmensdaten und ergänze fehlende Details.",
                "Review company details and fill any missing basics.",
            ),
            (
                "Nutze die Zusammenfassung oben, um fehlende Angaben gezielt zu ergänzen.",
                "Use the summary above to fill any missing details quickly.",
            ),
        ),
        required_fields=(),
        summary_fields=COMPANY_SUMMARY_FIELDS,
        allow_skip=False,
        renderer=_render_company_step,
    ),
    StepDefinition(
        key="team",
        label=("Abteilung & Team", "Department & Team"),
        panel_header=("Abteilung & Team", "Department & Team"),
        panel_subheader=("Struktur, Reporting & Rolle", "Structure, reporting & role"),
        panel_intro_variants=(
            (
                "Skizziere Abteilung, Teamstruktur und Reporting-Linie der Rolle.",
                "Outline department context, team structure, and reporting line for the role.",
            ),
            (
                "Präzise Angaben zu Seniorität, Reporting und Arbeitsmodell steuern Folgefragen.",
                "Precise details on seniority, reporting, and work setup guide follow-ups.",
            ),
            (
                "Erzähl kurz, wer die neue Person führt und ab wann es losgeht.",
                "Share who the new hire reports to and when they’ll get started.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "department.name",
            "team.name",
            "team.mission",
            "team.reporting_line",
            "team.headcount_current",
            "team.headcount_target",
            "team.collaboration_tools",
            "team.locations",
            "position.customer_contact_required",
            "position.customer_contact_details",
        ),
        allow_skip=False,
        renderer=_render_team_step,
        is_active=_team_step_active,
    ),
    StepDefinition(
        key="role_tasks",
        label=("Aufgaben & Skills", "Tasks & Skills"),
        panel_header=("Aufgaben & Skills", "Tasks & Skills"),
        panel_subheader=("Kernaufgaben & Skillbedarf", "Core tasks & skill needs"),
        panel_intro_variants=(
            (
                "Fasse zusammen, welche Aufgaben und Skills für die Rolle zentral sind.",
                "Summarise the core tasks and skills for this role.",
            ),
            (
                "Klare Aufgaben und Skills verbessern Anzeigen, Scorecards und Suchstrings.",
                "Clear tasks and skills improve job ads, scorecards, and searches.",
            ),
            (
                "Schreibe locker runter, woran die Person in den ersten Monaten wirklich arbeitet.",
                "Jot down what this person will tackle in the first months.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "responsibilities.items",
            "requirements.hard_skills_required",
            "requirements.soft_skills_required",
            "requirements.hard_skills_optional",
            "requirements.soft_skills_optional",
            "requirements.tools_and_technologies",
            "requirements.languages_required",
            "requirements.languages_optional",
            "requirements.certifications",
        ),
        allow_skip=False,
        renderer=_render_role_tasks_step,
    ),
    StepDefinition(
        key="skills",
        label=("Skills-Überblick", "Skills recap"),
        panel_header=("Skills-Überblick", "Skills recap"),
        panel_subheader=("Check & Feinschliff", "Review & refine"),
        panel_intro_variants=(
            (
                "Überprüfe die gesammelten Skills und korrigiere bei Bedarf.",
                "Review the captured skills and fine-tune as needed.",
            ),
            (
                "Ein kurzer Check sorgt für konsistente Exporte und Matching.",
                "A quick check keeps exports and matching consistent.",
            ),
            (
                "Passe fehlende Details an, falls nötig.",
                "Fill in any missing details if needed.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "requirements.hard_skills_required",
            "requirements.soft_skills_required",
            "requirements.hard_skills_optional",
            "requirements.soft_skills_optional",
            "requirements.tools_and_technologies",
            "requirements.languages_required",
            "requirements.languages_optional",
            "requirements.certifications",
        ),
        allow_skip=False,
        renderer=_render_skills_step,
    ),
    StepDefinition(
        key="benefits",
        label=("Benefits", "Benefits"),
        panel_header=("Benefits", "Benefits"),
        panel_subheader=("Vergütung & Zusatzleistungen", "Compensation & benefits"),
        panel_intro_variants=(
            (
                "Lege Gehaltsrahmen und Benefits transparent fest.",
                "Set a clear salary range and benefit package.",
            ),
            (
                "Strukturierte Vergütungsdaten verbessern Matching und Benchmarks.",
                "Structured compensation data improves matching and benchmarks.",
            ),
            (
                "Sag offen, was ihr zahlt und womit ihr Kandidat:innen begeistert.",
                "Be upfront about pay and the perks that excite candidates.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "compensation.salary_min",
            "compensation.salary_max",
            "compensation.currency",
            "compensation.period",
            "compensation.variable_pay",
            "compensation.bonus_percentage",
            "compensation.commission_structure",
            "compensation.equity_offered",
            "compensation.benefits",
            "employment.relocation_support",
            "employment.travel_required",
            "employment.visa_sponsorship",
        ),
        allow_skip=True,
        renderer=_render_benefits_step,
    ),
    StepDefinition(
        key="interview",
        label=("Recruiting-Prozess", "Recruitment process"),
        panel_header=("Recruiting-Prozess", "Recruitment process"),
        panel_subheader=("Phasen & Beteiligte", "Stages & stakeholders"),
        panel_intro_variants=(
            (
                "Skizziere Recruiting-Phasen, Dauer und beteiligte Personen für einen verlässlichen Ablauf.",
                "Map out the interview stages, timing, and stakeholders for a reliable journey.",
            ),
            (
                "Standardisierte Prozessdaten sichern Erwartungsmanagement, Candidate Experience und Auswertbarkeit.",
                "Standardised process data supports expectation management, candidate experience, and reporting.",
            ),
            (
                "Erzähl locker, wie Bewerber:innen durch euren Prozess gehen und wer sie dabei trifft.",
                "Give a quick rundown of how candidates move through your process and who they meet.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "process.phases",
            "process.stakeholders",
            "process.recruitment_timeline",
            "process.hiring_process",
            "process.process_notes",
            "process.application_instructions",
            "process.onboarding_process",
        ),
        allow_skip=True,
        renderer=_render_interview_step,
    ),
    StepDefinition(
        key="summary",
        label=("Zusammenfassung", "Summary"),
        panel_header=("Letzter Check & Export", "Final check & export"),
        panel_subheader=("Fehlende Pflichtfelder erkennen und schließen", "Spot and close any missing critical fields"),
        panel_intro_variants=(
            (
                "Prüfe die wichtigsten Angaben, wir zeigen offene Pflichtfelder direkt an.",
                "Review the key inputs; we highlight any remaining critical fields for you.",
            ),
            (
                "Eine letzte Validierung stellt konsistente Daten für Anzeigen, Reports und Integrationen sicher.",
                "A final validation keeps ads, reports, and integrations consistent.",
            ),
            (
                "Letzter Blick und offene Antworten schließen – danach kannst du exportieren oder teilen.",
                "Take a last look, close any gaps, and then export or share.",
            ),
        ),
        required_fields=(),
        summary_fields=(
            "summary.headline",
            "summary.value_proposition",
            "summary.culture_highlights",
            "summary.next_steps",
        ),
        allow_skip=False,
        renderer=_render_summary_step,
    ),
)


# Deprecated alias; use ``WIZARD_STEPS`` as the single source of truth.
STEPS: Final[tuple[StepDefinition, ...]] = WIZARD_STEPS


def step_keys() -> tuple[str, ...]:
    """Return wizard step keys in canonical order."""

    return tuple(step.key for step in WIZARD_STEPS)


def resolve_active_step_keys(profile: Mapping[str, object], session_state: Mapping[str, object]) -> tuple[str, ...]:
    """Return active wizard step keys in canonical order."""

    active: list[str] = []
    for step in WIZARD_STEPS:
        if step.is_active and not step.is_active(profile, session_state):
            continue
        active.append(step.key)
    return tuple(active)


def resolve_nearest_active_step_key(target_key: str, active_keys: Sequence[str]) -> str | None:
    """Return the nearest active step key for ``target_key``."""

    if target_key in active_keys:
        return target_key
    ordered_keys = step_keys()
    if target_key in ordered_keys:
        start_index = ordered_keys.index(target_key)
        for key in ordered_keys[start_index + 1 :]:
            if key in active_keys:
                return key
    return active_keys[0] if active_keys else None


def get_step(key: str) -> StepDefinition | None:
    """Lookup step metadata by key."""

    return next((step for step in WIZARD_STEPS if step.key == key), None)
