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


def test_parse_benefits_string() -> None:
    raw = '{"compensation": {"benefits": "30 Urlaubstage, Sabbatical-Option, 1.000€ Lernbudget"}}'
    jd = parse_extraction(raw)
    assert jd.compensation.benefits == [
        "30 Urlaubstage",
        "Sabbatical-Option",
        "1.000€ Lernbudget",
    ]


def test_parse_brand_name_alias() -> None:
    jd = parse_extraction('{"Brand Name": "Acme"}')
    assert jd.company.brand_name == "Acme"


def test_parse_application_deadline_alias() -> None:
    jd = parse_extraction('{"Application Deadline": "2024-12-31"}')
    assert jd.meta.application_deadline == "2024-12-31"


def test_parse_type_coercion() -> None:
    raw = (
        '{"employment": {"remote_percentage": "50%", "travel_required": "yes"},'
        ' "compensation": {"equity_offered": "false"},'
        ' "requirements": {"hard_skills_required": "Python, SQL"}}'
    )
    jd = parse_extraction(raw)
    assert jd.employment.remote_percentage == 50
    assert jd.employment.travel_required is True
    assert jd.compensation.equity_offered is False
    assert jd.requirements.hard_skills_required == ["Python", "SQL"]
