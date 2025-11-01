from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from pages.base import WizardPage


PAGES_DIR = Path(__file__).resolve().parents[1] / "pages"


def _iter_page_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted(PAGES_DIR.glob("[0-9][0-9]_*.py")):
        modules.append(f"pages.{path.stem}")
    return modules


@pytest.mark.parametrize("module_name", _iter_page_modules())
def test_wizard_pages_expose_metadata(module_name: str) -> None:
    module = import_module(module_name)

    assert hasattr(module, "PAGE"), f"{module_name} does not expose PAGE"
    page = module.PAGE
    assert isinstance(page, WizardPage)

    for lang in ("de", "en"):
        label = page.label_for(lang)
        assert isinstance(label, str) and label
        header = page.header_for(lang)
        assert isinstance(header, str) and header
        subheader = page.subheader_for(lang)
        assert isinstance(subheader, str) and subheader
        variants = list(page.intro_variants_for(lang))
        assert variants, f"{module_name} should expose intro variants"
        assert all(isinstance(text, str) and text for text in variants)
