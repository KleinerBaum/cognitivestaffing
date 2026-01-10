"""Wizard step metadata registry (CS_WIZARD_FLOW)."""

from __future__ import annotations

from wizard.step_registry import WIZARD_STEPS

from .base import WizardPage, page_from_step_definition


# Deprecated: ``wizard_pages`` now proxies the step registry to avoid drift.
# TODO: Remove this module once downstream imports use ``wizard.step_registry`` directly.
WIZARD_PAGES: tuple[WizardPage, ...] = tuple(page_from_step_definition(step) for step in WIZARD_STEPS)

__all__ = ["WizardPage", "WIZARD_PAGES", "page_from_step_definition"]
