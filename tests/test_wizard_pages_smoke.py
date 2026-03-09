from __future__ import annotations

from wizard.step_registry import WIZARD_STEPS
from wizard_pages import WIZARD_PAGES


def test_wizard_pages_have_registry_order() -> None:
    assert tuple(page.key for page in WIZARD_PAGES) == tuple(step.key for step in WIZARD_STEPS)


def test_wizard_pages_expose_bilingual_metadata() -> None:
    assert WIZARD_PAGES
    for page in WIZARD_PAGES:
        for lang in ("de", "en"):
            assert page.label_for(lang)
            assert page.header_for(lang)
            assert page.subheader_for(lang)
            variants = tuple(page.intro_variants_for(lang))
            assert variants
            assert all(isinstance(item, str) and item for item in variants)
