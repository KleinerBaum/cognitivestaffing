from __future__ import annotations

from sidebar import _render_step_context
from wizard.step_registry import WIZARD_STEPS
from wizard_pages import WIZARD_PAGES
from wizard_pages.base import page_from_step_definition


def test_wizard_pages_proxy_step_registry() -> None:
    expected_pages = tuple(page_from_step_definition(step) for step in WIZARD_STEPS)

    assert WIZARD_PAGES == expected_pages


def test_step_keys_stay_in_sync_between_registry_and_pages() -> None:
    step_keys = tuple(step.key for step in WIZARD_STEPS)
    page_keys = tuple(page.key for page in WIZARD_PAGES)

    assert page_keys == step_keys


def test_sidebar_step_context_renderer_covers_all_registered_steps() -> None:
    renderers = _render_step_context.__globals__["_STEP_CONTEXT_RENDERERS"]
    registry_keys = {step.key for step in WIZARD_STEPS}

    assert registry_keys.issubset(set(renderers))
