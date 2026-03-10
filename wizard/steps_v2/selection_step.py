from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_selection(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Selection", "Selection"),
        intro=(
            "Definiere Auswahlprozess und Stakeholder transparent.",
            "Define selection process and stakeholder setup clearly.",
        ),
        missing_paths=("selection.process_steps",),
        known_fields=(("Process steps", "selection.process_steps"), ("Stakeholders", "selection.stakeholders")),
    )
