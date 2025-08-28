import json
from llm.client import OPENAI_CLIENT, extract_and_parse


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.output_text = text
        self.output: list[dict[str, str]] = []
        self.usage: dict[str, int] = {}


def fake_create(**kwargs):
    payload = {"company": {"name": "Acme"}, "position": {"job_title": "Dev"}}
    return _FakeResponse(json.dumps(payload))


def test_extract_and_parse(monkeypatch) -> None:
    monkeypatch.setattr(OPENAI_CLIENT.responses, "create", fake_create)
    out = extract_and_parse("text")
    assert out.company.name == "Acme"
    assert out.position.job_title == "Dev"
