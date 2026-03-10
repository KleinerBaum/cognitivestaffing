"""Wizard step metadata registry (CS_WIZARD_FLOW)."""

from __future__ import annotations

from wizard.step_registry import WIZARD_STEPS

from .base import WizardPage, page_from_step_definition


WIZARD_PAGES: tuple[WizardPage, ...] = tuple(page_from_step_definition(step) for step in WIZARD_STEPS)


def pages_for_version(version: str) -> tuple[WizardPage, ...]:
    """Return wizard pages for the requested version."""

    from wizard.step_registry_runtime import get_wizard_steps

    return tuple(page_from_step_definition(step) for step in get_wizard_steps(version))


__all__ = ["WizardPage", "WIZARD_PAGES", "page_from_step_definition", "pages_for_version"]
