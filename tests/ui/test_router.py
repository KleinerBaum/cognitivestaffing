from __future__ import annotations

from wizard.flow import STEP_RENDERERS
from wizard.step_registry import step_keys
from wizard_pages import WIZARD_PAGES


def test_step_order() -> None:
    keys = [page.key for page in WIZARD_PAGES]
    assert tuple(keys) == step_keys()
    assert keys[:2] == ["landing", "jobad"]


def test_renderer_mapping_covers_all_step_keys() -> None:
    for key in step_keys():
        assert key in STEP_RENDERERS
