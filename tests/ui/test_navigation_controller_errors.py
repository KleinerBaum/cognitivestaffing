from __future__ import annotations

from typing import Any

from wizard.navigation import NavigationController


class _StubPage:
    def __init__(self, key: str, label_de: str, label_en: str) -> None:
        self.key = key
        self._labels = {"de": label_de, "en": label_en}

    def label_for(self, lang: str) -> str:
        return self._labels[lang]


def _capture_render(monkeypatch: Any) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _fake_render(message_de: str, message_en: str, error: Exception | None = None) -> None:
        captured["message_de"] = message_de
        captured["message_en"] = message_en
        captured["error"] = error

    monkeypatch.setattr("wizard._logic._render_localized_error", _fake_render)
    return captured


def test_handle_step_exception_surfaces_ai_guidance(monkeypatch: Any) -> None:
    class _FakeBadRequestError(Exception):
        pass

    monkeypatch.setattr("wizard.navigation.router.BadRequestError", _FakeBadRequestError)
    captured = _capture_render(monkeypatch)
    controller = object.__new__(NavigationController)
    page = _StubPage("team", "Team", "Team")

    controller.handle_step_exception(page, _FakeBadRequestError("invalid"))

    assert "KI konnte" in str(captured["message_de"])
    assert "could not generate" in str(captured["message_en"])


def test_handle_step_exception_prompts_for_update_on_config_error(monkeypatch: Any) -> None:
    captured = _capture_render(monkeypatch)
    controller = object.__new__(NavigationController)
    page = _StubPage("team", "Team", "Team")

    controller.handle_step_exception(page, KeyError("TEAM_HELP_TEXT"))

    assert "Konfigurationsdaten" in str(captured["message_de"])
    assert "Configuration data" in str(captured["message_en"])
