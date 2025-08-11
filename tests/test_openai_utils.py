def test_responses_json_parses(monkeypatch):
    from core import openai_utils

    class DummyResp:
        def __init__(self, text: str) -> None:
            self.output = [{"content": [{"type": "output_text", "text": text}]}]

    class Client:
        responses = type(
            "R", (), {"create": staticmethod(lambda **_: DummyResp('{"foo": 1}'))}
        )()

    monkeypatch.setattr(openai_utils, "_client", Client())
    data = openai_utils.responses_json(model="gpt")
    assert data == {"foo": 1}


def test_responses_json_invalid(monkeypatch):
    from core import openai_utils
    import pytest

    class DummyResp:
        def __init__(self, text: str) -> None:
            self.output = [{"content": [{"type": "output_text", "text": text}]}]

    class Client:
        responses = type(
            "R", (), {"create": staticmethod(lambda **_: DummyResp("not json"))}
        )()

    monkeypatch.setattr(openai_utils, "_client", Client())
    with pytest.raises(ValueError):
        openai_utils.responses_json(model="gpt")
