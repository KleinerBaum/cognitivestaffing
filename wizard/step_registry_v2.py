"""Dedicated step registry for the V2 wizard flow."""

from __future__ import annotations

from typing import Final

from wizard.navigation_types import WizardContext
from wizard.step_registry import StepDefinition
from wizard.steps_v2 import (
    step_constraints,
    step_hiring_goal,
    step_intake,
    step_real_work,
    step_requirements_board,
    step_review,
    step_selection,
)


def _render_intake(context: WizardContext) -> None:
    step_intake(context)


def _render_hiring_goal(context: WizardContext) -> None:
    step_hiring_goal(context)


def _render_real_work(context: WizardContext) -> None:
    step_real_work(context)


def _render_requirements_board(context: WizardContext) -> None:
    step_requirements_board(context)


def _render_constraints(context: WizardContext) -> None:
    step_constraints(context)


def _render_selection(context: WizardContext) -> None:
    step_selection(context)


def _render_review(context: WizardContext) -> None:
    step_review(context)


WIZARD_STEPS_V2: Final[tuple[StepDefinition, ...]] = (
    StepDefinition(
        key="intake",
        label=("Intake", "Intake"),
        panel_header=("Intake", "Intake"),
        panel_subheader=("Ausgangslage", "Starting point"),
        panel_intro_variants=(("Eingangsdaten prüfen.", "Review incoming data."),),
        required_fields=("intake.raw_input",),
        summary_fields=("intake.source_language", "intake.target_locale"),
        allow_skip=False,
        renderer=_render_intake,
    ),
    StepDefinition(
        key="hiring_goal",
        label=("Hiring Goal", "Hiring Goal"),
        panel_header=("Hiring Goal", "Hiring Goal"),
        panel_subheader=("Zielbild", "Target profile"),
        panel_intro_variants=(("Zielprofil schärfen.", "Clarify target profile."),),
        required_fields=("role.title", "role.summary"),
        summary_fields=("role.title", "role.seniority", "role.department", "role.team"),
        allow_skip=False,
        renderer=_render_hiring_goal,
    ),
    StepDefinition(
        key="real_work",
        label=("Real Work", "Real Work"),
        panel_header=("Real Work", "Real Work"),
        panel_subheader=("Tagesgeschäft", "Day-to-day work"),
        panel_intro_variants=(("Kernaufgaben konkretisieren.", "Specify core responsibilities."),),
        required_fields=("work.responsibilities",),
        summary_fields=("work.responsibilities", "work.location", "work.work_policy"),
        allow_skip=False,
        renderer=_render_real_work,
    ),
    StepDefinition(
        key="requirements_board",
        label=("Requirements Board", "Requirements Board"),
        panel_header=("Requirements Board", "Requirements Board"),
        panel_subheader=("Muss / Kann", "Must / Nice"),
        panel_intro_variants=(("Anforderungen priorisieren.", "Prioritize requirements."),),
        required_fields=("requirements.hard_skills_required",),
        summary_fields=(
            "requirements.hard_skills_required",
            "requirements.soft_skills_required",
            "requirements.languages_required",
        ),
        allow_skip=False,
        renderer=_render_requirements_board,
    ),
    StepDefinition(
        key="constraints",
        label=("Constraints", "Constraints"),
        panel_header=("Constraints", "Constraints"),
        panel_subheader=("Rahmenbedingungen", "Guardrails"),
        panel_intro_variants=(("Fixe Rahmenbedingungen festhalten.", "Capture fixed constraints."),),
        required_fields=("constraints.timeline",),
        summary_fields=("constraints.salary_min", "constraints.salary_max", "constraints.timeline"),
        allow_skip=False,
        renderer=_render_constraints,
    ),
    StepDefinition(
        key="selection",
        label=("Selection", "Selection"),
        panel_header=("Selection", "Selection"),
        panel_subheader=("Auswahlprozess", "Selection process"),
        panel_intro_variants=(("Auswahlprozess abstimmen.", "Align on selection process."),),
        required_fields=("selection.process_steps",),
        summary_fields=("selection.process_steps", "selection.stakeholders"),
        allow_skip=False,
        renderer=_render_selection,
    ),
    StepDefinition(
        key="review",
        label=("Review", "Review"),
        panel_header=("Review", "Review"),
        panel_subheader=("Finale Entscheidungen", "Final decisions"),
        panel_intro_variants=(("Offene Entscheidungen finalisieren.", "Finalize open decisions."),),
        required_fields=(),
        summary_fields=("open_decisions", "warnings"),
        allow_skip=False,
        renderer=_render_review,
    ),
)


def step_keys_v2() -> tuple[str, ...]:
    return tuple(step.key for step in WIZARD_STEPS_V2)


def get_step_v2(key: str) -> StepDefinition | None:
    return next((step for step in WIZARD_STEPS_V2 if step.key == key), None)
