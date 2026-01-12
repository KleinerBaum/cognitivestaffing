from __future__ import annotations

import pytest

from llm.response_schemas import SKILL_SUGGESTION_SCHEMA_NAME, get_response_schema
from utils.json_repair import JsonRepairStatus
from utils.skill_suggestions import parse_skill_suggestions_payload


def _schema():
    return get_response_schema(SKILL_SUGGESTION_SCHEMA_NAME)


def test_parse_skill_suggestions_valid_json() -> None:
    raw = (
        '{"tools_and_technologies":["Docker"],'
        '"hard_skills":["Python"],'
        '"soft_skills":["Communication"],'
        '"certificates":["AWS Certified"]}'
    )
    result = parse_skill_suggestions_payload(
        raw,
        schema_name=SKILL_SUGGESTION_SCHEMA_NAME,
        schema=_schema(),
        allow_llm_repair=False,
    )

    assert result.payload is not None
    assert result.payload["tools_and_technologies"] == ["Docker"]
    assert result.status is JsonRepairStatus.OK


def test_parse_skill_suggestions_repairs_codefence() -> None:
    raw = (
        "```json\n"
        '{"tools_and_technologies":["Kubernetes"],'
        '"hard_skills":["Go"],'
        '"soft_skills":["Collaboration"],'
        '"certificates":["CKA"]}'
        "\n```"
    )
    result = parse_skill_suggestions_payload(
        raw,
        schema_name=SKILL_SUGGESTION_SCHEMA_NAME,
        schema=_schema(),
        allow_llm_repair=False,
    )

    assert result.payload is not None
    assert result.payload["hard_skills"] == ["Go"]
    assert result.status is JsonRepairStatus.REPAIRED


def test_parse_skill_suggestions_missing_required_keys() -> None:
    raw = '{"tools_and_technologies":["Terraform"],"hard_skills":[],"soft_skills":[]}'
    with pytest.raises(ValueError, match="does not match schema"):
        parse_skill_suggestions_payload(
            raw,
            schema_name=SKILL_SUGGESTION_SCHEMA_NAME,
            schema=_schema(),
            allow_llm_repair=False,
        )
