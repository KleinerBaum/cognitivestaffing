"""Tests for vacancy profile extraction via Responses API."""

import llm.extract_profile as ep


def test_extract_profile_parses_tool_output(monkeypatch):
    """Structured tool output should validate into VacancyProfile."""

    class _FakeFunction:
        def __init__(self) -> None:
            self.name = "emit_profile"
            self.arguments = {"title": "Engineer"}

    class _FakeToolCall:
        def __init__(self) -> None:
            self.function = _FakeFunction()

    class _FakeOutput:
        def __init__(self) -> None:
            self.type = "tool_call"
            self.tool_call = _FakeToolCall()

    class _FakeResponse:
        def __init__(self) -> None:
            self.output = [_FakeOutput()]
            self.usage: dict = {}

        def model_dump(self) -> dict:
            return {
                "output": [
                    {
                        "tool_call": {
                            "function": {
                                "name": "emit_profile",
                                "arguments": {"title": "Engineer"},
                            }
                        }
                    }
                ]
            }

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        class responses:
            @staticmethod
            def create(**kwargs):
                return _FakeResponse()

    monkeypatch.setattr(ep, "OpenAI", _FakeClient)

    result = ep.extract_profile_from_text("dummy")
    assert result.ok
    assert result.profile.title == "Engineer"
