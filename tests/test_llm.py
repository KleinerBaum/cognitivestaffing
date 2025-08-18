import json
from llm.client import extract_and_parse, OPENAI_CLIENT


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content
        self.function_call = None


class _Choice:
    def __init__(self, msg: _Msg) -> None:
        self.message = msg


class _Resp:
    def __init__(self, msg: _Msg) -> None:
        self.choices = [_Choice(msg)]


def fake_create(**kwargs):
    payload = {"company": {"name": "Acme"}, "position": {"job_title": "Dev"}}
    return _Resp(_Msg(json.dumps(payload)))


def test_extract_and_parse(monkeypatch) -> None:
    monkeypatch.setattr(OPENAI_CLIENT.chat.completions, "create", fake_create)
    out = extract_and_parse("text")
    assert out.company.name == "Acme"
    assert out.position.job_title == "Dev"
