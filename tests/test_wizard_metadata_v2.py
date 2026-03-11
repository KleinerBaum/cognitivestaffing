from __future__ import annotations

from wizard.metadata import (
    PAGE_FIELD_MAP,
    PAGE_FOLLOWUP_PREFIXES,
    PAGE_PROGRESS_FIELDS,
    PAGE_SECTION_INDEXES,
    validate_step_metadata_consistency,
)
from wizard.missing_fields import group_missing_fields_by_step
from wizard.validation import missing_inline_followups
from wizard_pages import pages_for_version


def test_v2_page_mappings_present() -> None:
    assert PAGE_SECTION_INDEXES["intake"] == 0
    assert PAGE_SECTION_INDEXES["hiring_goal"] == 1
    assert PAGE_SECTION_INDEXES["real_work"] == 2
    assert PAGE_SECTION_INDEXES["requirements_board"] == 3
    assert PAGE_SECTION_INDEXES["constraints"] == 4
    assert PAGE_SECTION_INDEXES["selection"] == 5
    assert PAGE_SECTION_INDEXES["review"] == 6

    assert PAGE_FOLLOWUP_PREFIXES["intake"] == ("intake.",)
    assert PAGE_FOLLOWUP_PREFIXES["hiring_goal"] == ("role.",)
    assert PAGE_FOLLOWUP_PREFIXES["real_work"] == ("work.",)
    assert PAGE_FOLLOWUP_PREFIXES["constraints"] == ("constraints.",)


def test_v2_progress_fields_include_required_and_summary_fields() -> None:
    hiring_goal_fields = PAGE_PROGRESS_FIELDS["hiring_goal"]
    assert "role.title" in hiring_goal_fields
    assert "role.seniority" in hiring_goal_fields
    assert PAGE_FIELD_MAP["role.seniority"] == "hiring_goal"

    review_fields = PAGE_PROGRESS_FIELDS["review"]
    assert "open_decisions" in review_fields
    assert "warnings" in review_fields
    assert PAGE_FIELD_MAP["warnings"] == "review"


def test_validate_step_metadata_consistency_for_v2_pages() -> None:
    errors = validate_step_metadata_consistency(pages_for_version("v2"))
    assert errors == []


def test_missing_inline_followups_supports_v2_prefixes() -> None:
    page = next(step for step in pages_for_version("v2") if step.key == "constraints")
    missing = missing_inline_followups(
        page,
        profile={"constraints": {}},
        followups=[
            {"field": "constraints.timeline", "priority": "critical", "question": "When?"},
            {"field": "constraints.notes", "priority": "optional", "question": "Notes?"},
        ],
        session_state={},
    )
    assert missing == ["constraints.timeline"]


def test_group_missing_fields_by_step_uses_v2_ownership() -> None:
    grouped = group_missing_fields_by_step(["role.title", "constraints.timeline", "warnings"])
    assert grouped["hiring_goal"] == ["role.title"]
    assert grouped["constraints"] == ["constraints.timeline"]
    assert grouped["review"] == ["warnings"]
