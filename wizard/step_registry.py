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


def _render_jobad_step(context: WizardContext) -> None:
    from wizard.steps import jobad_step

    jobad_step.step_jobad(context)


def _render_company_step(context: WizardContext) -> None:
    from wizard.steps import company_step

    company_step.step_company(context)


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
    ),
    StepDefinition(
        key="company",
        label=("Unternehmen", "Company"),
        panel_header=("Unternehmen", "Company"),
        panel_subheader=("Profil & Kontakt", "Profile & contact"),
        panel_intro_variants=(
            (
                "Falls nichts erkannt wurde, ergänze Name, Branche und Kontakt – sonst bitte kurz prüfen und bestätigen.",
                "If nothing was detected, add name, industry, and contact details – otherwise just review and confirm.",
            ),
            (
                "Wir haben Felder aus der Anzeige übernommen; passe sie an, wenn der Job-Text unvollständig war.",
                "We pre-filled fields from the job ad; tweak them if the posting was incomplete.",
            ),
        ),
        required_fields=(
            "company.name",
            "company.contact_email",
            "department.name",
            "location.primary_city",
        ),
        summary_fields=(
            "company.name",
            "company.legal_name",
            "company.brand_name",
            "company.tagline",
            "company.industry",
            "company.industries",
            "company.size",
            "company.website",
            "company.mission",
            "company.hq_location",
            "company.locations",
            "company.culture",
            "company.values",
            "company.brand_keywords",
            "company.description",
            "company.contact_name",
            "company.contact_email",
            "company.contact_phone",
            "company.logo_url",
            "company.brand_color",
            "company.claim",
            "company.benefits",
            "department.name",
            "department.function",
            "department.leader_name",
            "department.leader_title",
            "department.strategic_goals",
        ),
        allow_skip=False,
        renderer=_render_company_step,
    ),
    StepDefinition(
        key="team",
        label=("Team & Struktur", "Team & Structure"),
        panel_header=("Team & Struktur", "Team & Structure"),
        panel_subheader=("Berichtslinien & Teamaufbau", "Reporting & team setup"),
        panel_intro_variants=(
            (
                "Skizziere Struktur, Berichtslinien und Startzeitpunkt der Rolle.",
                "Outline the team structure, reporting line, and start timing for the role.",
            ),
            (
                "Präzise Angaben zu Seniorität, Reporting und Standort steuern Folgefragen und Automatisierung.",
                "Precise details on seniority, reporting, and location inform follow-up prompts and automation.",
            ),
            (
                "Erzähl kurz, wer die neue Person an die Hand nimmt und ab wann es losgeht.",
                "Let us know who the new hire reports to and when they’ll get started.",
            ),
        ),
        required_fields=(
            "team.reporting_line",
            "position.reporting_manager_name",
            "position.job_title",
        ),
        summary_fields=(
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
        label=("Rolle & Aufgaben", "Role & Tasks"),
        panel_header=("Rolle & Aufgaben", "Role & Tasks"),
        panel_subheader=("Deliverables & Wirkung", "Deliverables & impact"),
        panel_intro_variants=(
            (
                "Fasse zusammen, welche Ergebnisse die Rolle kurzfristig liefern muss.",
                "Summarise the outcomes this role needs to deliver in the near term.",
            ),
            (
                "Konkret benannte Deliverables helfen bei Automatisierung von Anzeigen, Scorecards und Onboarding.",
                "Explicit deliverables feed automation for job ads, scorecards, and onboarding.",
            ),
            (
                "Schreibe locker runter, woran die Person in den ersten Monaten wirklich arbeitet.",
                "Jot down what this person will actually be tackling in the first months.",
            ),
        ),
        required_fields=(
            "responsibilities.items",
            "requirements.hard_skills_required",
        ),
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
        label=("Fähigkeiten & Anforderungen", "Skills & Requirements"),
        panel_header=("Skills & Anforderungen", "Skills & Requirements"),
        panel_subheader=("Pflicht & Nice-to-have", "Must-have & nice-to-have"),
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
        label=("Vergütung", "Compensation"),
        panel_header=("Vergütung", "Compensation"),
        panel_subheader=("Gehalt & Zusatzleistungen", "Salary & benefits"),
        panel_intro_variants=(
            (
                "Lege Gehaltsrahmen, Bonusmodell und Benefits transparent fest.",
                "Set a clear salary range, bonus model, and benefit package.",
            ),
            (
                "Strukturierte Vergütungsdaten verbessern Marktplatz-Matching, Benchmarks und Angebotsunterlagen.",
                "Structured compensation data improves marketplace matching, benchmarking, and offer collateral.",
            ),
            (
                "Sag offen, was ihr zahlt und womit ihr Kandidat:innen begeistert.",
                "Be upfront about pay and the perks that make candidates excited.",
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
        label=("Bewerbungsprozess", "Hiring Process"),
        panel_header=("Bewerbungsprozess", "Hiring Process"),
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
        required_fields=("process.phases",),
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
