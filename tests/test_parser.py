import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from utils.json_parse import parse_extraction  # noqa: E402


def test_parse_pure_json() -> None:
    jd = parse_extraction('{"position": {"job_title": "Dev"}}')
    assert jd.position.job_title == "Dev"


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"position": {"job_title": "Dev"}}\n```',
        'Here is the data: {"position": {"job_title": "Dev"}} Thanks',
    ],
)
def test_parse_with_sanitization(raw: str) -> None:
    jd = parse_extraction(raw)
    assert jd.position.job_title == "Dev"


def test_parse_mismatched_quotes() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_extraction('{"position": {"job_title": "Dev"}')
