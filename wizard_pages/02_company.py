from __future__ import annotations

# Deprecated: keep module for backwards-compatible imports.
# TODO: Remove this module once downstream imports use ``wizard.step_registry`` directly.
from wizard.step_registry import get_step
from wizard_pages.base import page_from_step_definition


_STEP = get_step("company")
if _STEP is None:
    raise ImportError("Wizard step registry missing 'company' definition.")

PAGE = page_from_step_definition(_STEP)
