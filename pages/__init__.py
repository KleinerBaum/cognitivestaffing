"""Wizard step metadata registry (CS_WIZARD_FLOW)."""

from __future__ import annotations

from importlib import util
from pathlib import Path
from types import ModuleType
from typing import Iterable

from pages.base import WizardPage


def _load_page_module(filename: str) -> ModuleType:
    base_path = Path(__file__).resolve().parent
    spec = util.spec_from_file_location(
        f"pages._{filename}",
        base_path / f"{filename}.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load wizard page: {filename}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pages() -> Iterable[WizardPage]:
    for name in (
        "01_jobad",
        "02_company",
        "03_team",
        "04_role_tasks",
        "05_skills",
        "06_benefits",
        "07_interview",
        "08_summary",
    ):
        module = _load_page_module(name)
        page = getattr(module, "PAGE", None)
        if not isinstance(page, WizardPage):
            raise AttributeError(f"Wizard page '{name}' does not define PAGE metadata")
        yield page


WIZARD_PAGES: tuple[WizardPage, ...] = tuple(_load_pages())

__all__ = ["WizardPage", "WIZARD_PAGES"]
