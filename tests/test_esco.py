import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.esco_utils import normalize_skills  # noqa: E402
from questions.augment import missing_esco_skills  # noqa: E402


def test_normalize_skills(monkeypatch) -> None:
    def fake_lookup(skill, lang="en"):
        return {"preferredLabel": skill.strip().title()}

    monkeypatch.setattr("core.esco_utils.lookup_esco_skill", fake_lookup)
    out = normalize_skills(["python", "Python ", "docker", ""])
    assert out == ["Python", "Docker"]


def test_missing_esco_skills(monkeypatch) -> None:
    def fake_get(uri, lang="en"):
        return ["Git", "Python", "Docker"]

    monkeypatch.setattr("questions.augment.get_essential_skills", fake_get)
    missing = missing_esco_skills("uri", ["Python"], ["Docker"])
    assert missing == ["Git"]
