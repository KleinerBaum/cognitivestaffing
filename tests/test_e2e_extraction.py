import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest  # noqa: E402
from core.ss_bridge import to_session_state  # noqa: E402
from llm.client import extract_and_parse  # noqa: E402


@pytest.mark.parametrize(
    "raw",
    [
        '{"position": {"job_title": "Dev"}}',
        '```json\n{"position": {"job_title": "Dev"}}\n```',
        'Noise {"position": {"job_title": "Dev"}} tail',
    ],
)
def test_e2e_to_session_state(monkeypatch, raw: str) -> None:
    """End-to-end extraction should populate session state."""

    def fake_extract_json(text, title=None, url=None, minimal=False):
        return raw

    monkeypatch.setattr("llm.client.extract_json", fake_extract_json)
    jd = extract_and_parse("input")
    ss: dict = {}
    to_session_state(jd, ss)
    assert ss["position.job_title"] == "Dev"
