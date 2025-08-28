import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import openai_utils
from openai_utils import ChatCallResult, suggest_skills_for_role


def fake_call(messages, **kwargs):
    payload = json.dumps(
        {
            "tools_and_technologies": [f"T{i}" for i in range(1, 12)],
            "hard_skills": ["H1", "H1", "H2"],
            "soft_skills": ["S1", "S2"],
        }
    )
    return ChatCallResult(payload, [], {})


def test_suggest_skills_for_role(monkeypatch):
    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call)
    monkeypatch.setattr(
        "core.esco_utils.normalize_skills", lambda skills, lang="en": skills
    )
    out = suggest_skills_for_role("Engineer")
    assert out["tools_and_technologies"] == [f"T{i}" for i in range(1, 11)]
    assert out["hard_skills"] == ["H1", "H2"]
    assert out["soft_skills"] == ["S1", "S2"]


def test_suggest_skills_for_role_empty():
    out = suggest_skills_for_role("")
    assert out == {
        "tools_and_technologies": [],
        "hard_skills": [],
        "soft_skills": [],
    }
