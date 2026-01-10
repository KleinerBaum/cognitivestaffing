from __future__ import annotations

from wizard.step_registry import WIZARD_STEPS
from wizard_pages import WIZARD_PAGES
from wizard_pages.base import page_from_step_definition


def test_wizard_pages_proxy_step_registry() -> None:
    expected_pages = tuple(page_from_step_definition(step) for step in WIZARD_STEPS)

    assert WIZARD_PAGES == expected_pages
