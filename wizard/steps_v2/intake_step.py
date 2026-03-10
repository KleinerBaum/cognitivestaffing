from __future__ import annotations

from wizard.navigation_types import WizardContext

from ._shared import render_v2_step


def step_intake(context: WizardContext) -> None:
    render_v2_step(
        context,
        title=("Intake", "Intake"),
        intro=(
            "Prüfe die importierten Ausgangsdaten als Basis für die nächsten Entscheidungen.",
            "Review imported intake data as the baseline for downstream decisions.",
        ),
        missing_paths=("intake.raw_input",),
        known_fields=(
            ("Source language", "intake.source_language"),
            ("Target locale", "intake.target_locale"),
        ),
    )
