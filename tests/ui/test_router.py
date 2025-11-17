from __future__ import annotations

from pages import WIZARD_PAGES


def test_step_order() -> None:
    keys = [page.key for page in WIZARD_PAGES]
    assert keys == [
        "jobad",
        "company",
        "team",
        "role_tasks",
        "skills",
        "benefits",
        "interview",
        "summary",
    ]
