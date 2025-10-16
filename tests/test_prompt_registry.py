from prompts import PromptRegistry, prompt_registry


def test_prompt_registry_loads_default_path() -> None:
    value = prompt_registry.get("llm.json_extractor.system")
    assert "You are an extractor" in value


def test_prompt_registry_locale_resolution() -> None:
    german = prompt_registry.get("llm.interview_guide.system", locale="de-DE")
    english = prompt_registry.get("llm.interview_guide.system", locale="en")
    assert "HR-Coachin" in german
    assert "experienced HR coach" in english


def test_prompt_registry_formatting(tmp_path) -> None:
    registry_file = tmp_path / "registry.json"
    registry_file.write_text('{"example": {"system": "Call {name}"}}', encoding="utf-8")
    registry = PromptRegistry(path=registry_file)
    assert registry.format("example.system", name="Alice") == "Call Alice"
