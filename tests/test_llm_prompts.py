from llm.prompts import (
    FIELDS_ORDER_QUICK,
    build_user_json_extract_prompt,
    render_field_bullets,
)
from core.schema import ALL_FIELDS


def test_user_template_enumerates_all_fields() -> None:
    prompt = build_user_json_extract_prompt(ALL_FIELDS, "text", {})
    for field in ALL_FIELDS:
        assert f"- {field}" in prompt


def test_render_field_bullets_matches_order() -> None:
    expected = "\n".join(f"- {f}" for f in ALL_FIELDS)
    assert render_field_bullets() == expected


def test_quick_field_subset_is_smaller() -> None:
    assert set(FIELDS_ORDER_QUICK).issubset(set(ALL_FIELDS))
    assert len(FIELDS_ORDER_QUICK) < len(ALL_FIELDS)
