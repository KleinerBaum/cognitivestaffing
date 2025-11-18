import json

from pydantic import ValidationError

from llm.output_parsers import NeedAnalysisOutputParser
from models.need_analysis import NeedAnalysisProfile


def test_stage_error_detection_handles_nested_locations() -> None:
    """Nested validation locations for interview stages should be detected."""

    parser = NeedAnalysisOutputParser()
    validation_error = ValidationError.from_exception_data(
        NeedAnalysisProfile.__name__,
        [
            {
                "type": "int_parsing",
                "loc": ("process", "interview_stages", 0),
                "msg": "Input should be a valid integer",
                "input": ["phone", "onsite"],
            }
        ],
    )

    assert parser._has_interview_stage_error(validation_error) is True


def test_stage_sequences_are_coerced_to_counts() -> None:
    """List-based stage payloads should be coerced to integer counts."""

    parser = NeedAnalysisOutputParser()
    payload = NeedAnalysisProfile().model_dump()
    payload["process"]["interview_stages"] = ["Phone screen", "Case study"]

    changed = parser._coerce_stage_list(payload)

    assert changed is True
    assert payload["process"]["interview_stages"] == 2


def test_parser_can_normalize_nested_stage_list() -> None:
    """The full parser should normalize interview stage lists inside JSON payloads."""

    parser = NeedAnalysisOutputParser()
    profile_payload = NeedAnalysisProfile().model_dump()
    profile_payload["process"]["interview_stages"] = ["Phone", "Onsite"]
    structured = json.dumps({"profile": profile_payload})

    model, data = parser.parse(structured)

    assert model.process.interview_stages == 2
    assert data["process"]["interview_stages"] == 2
