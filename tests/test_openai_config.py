import importlib
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import config.models as model_config
import core.schema as schema_module

from constants.keys import StateKeys
from models.need_analysis import NeedAnalysisProfile
from pydantic import ValidationError

es = importlib.import_module("state.ensure_state")


def test_missing_api_key_sets_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "", raising=False)
    es.ensure_state()
    assert st.session_state["openai_api_key_missing"] is True


def test_invalid_base_url_sets_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "not a url", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "not a url", raising=False)
    es.ensure_state()
    assert st.session_state["openai_base_url_invalid"] is True


def test_valid_base_url_us_does_not_set_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "https://api.openai.com/v1", raising=False)

    try:
        es.ensure_state()
        assert st.session_state["openai_base_url_invalid"] is False
    finally:
        st.session_state.clear()


def test_valid_base_url_eu_does_not_set_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://eu.api.openai.com/v1", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "https://eu.api.openai.com/v1", raising=False)

    try:
        es.ensure_state()
        assert st.session_state["openai_base_url_invalid"] is False
    finally:
        st.session_state.clear()


def test_ensure_state_normalises_legacy_models():
    st.session_state.clear()
    st.session_state["model"] = model_config.GPT4O
    st.session_state["model_override"] = model_config.GPT4O_MINI
    es.ensure_state()
    assert st.session_state["model"] == model_config.GPT4O
    assert "model_override" not in st.session_state


def test_ensure_state_preserves_minimal_reasoning_level():
    st.session_state.clear()
    st.session_state[StateKeys.REASONING_EFFORT] = "minimal"

    es.ensure_state()

    assert st.session_state[StateKeys.REASONING_EFFORT] == "minimal"


def test_ensure_state_salvages_profile_with_extra_fields():
    st.session_state.clear()
    profile = NeedAnalysisProfile().model_dump()
    profile["company"]["name"] = "ACME GmbH"
    profile["position"]["job_title"] = "Data Scientist"
    profile["requirements"]["hard_skills_required"] = ["Python"]
    profile["date_of_employment_start"] = "2024-11-01"
    profile["unknown_section"] = {"foo": "bar"}
    profile["company"]["invalid_field"] = "ignore me"

    st.session_state[StateKeys.PROFILE] = profile

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"
    assert result["requirements"]["hard_skills_required"] == ["Python"]
    assert result["meta"]["target_start_date"] == "2024-11-01"
    assert "unknown_section" not in result
    assert "invalid_field" not in result["company"]


def _build_profile_with_invalid_stage() -> dict[str, object]:
    profile = NeedAnalysisProfile().model_dump()
    profile["company"]["name"] = "ACME GmbH"
    profile["position"]["job_title"] = "Data Scientist"
    profile["process"]["interview_stages"] = ["Phone screen", "Case Study"]
    return profile


def test_ensure_state_repairs_invalid_profile_fields(monkeypatch):
    st.session_state.clear()
    invalid_profile = _build_profile_with_invalid_stage()
    st.session_state[StateKeys.PROFILE] = deepcopy(invalid_profile)

    monkeypatch.setattr(schema_module, "repair_profile_payload", lambda *_, **__: None)

    repaired_profile = deepcopy(invalid_profile)
    repaired_profile["process"]["interview_stages"] = 2

    def fake_repair(payload, errors=None):  # type: ignore[unused-ignore]
        assert payload["process"]["interview_stages"] == ["Phone screen", "Case Study"]
        assert errors
        return repaired_profile

    monkeypatch.setattr(es, "repair_profile_payload", fake_repair)

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"
    assert result["process"]["interview_stages"] == 2


def test_ensure_state_normalises_interview_stage_list_without_json_repair(monkeypatch):
    st.session_state.clear()
    invalid_profile = _build_profile_with_invalid_stage()
    st.session_state[StateKeys.PROFILE] = invalid_profile

    monkeypatch.setattr(schema_module, "repair_profile_payload", lambda *_, **__: None)
    monkeypatch.setattr(es, "repair_profile_payload", lambda *_, **__: None)

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"
    assert result["process"]["interview_stages"] == 2


def test_ensure_state_sets_summary_when_profile_reset(monkeypatch):
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
    st.session_state[StateKeys.PROFILE] = {"company": {"contact_email": {"bad": "value"}}}

    def _make_error() -> ValidationError:
        return ValidationError.from_exception_data(
            NeedAnalysisProfile.__name__,
            [
                {
                    "type": "string_type",
                    "loc": ("company", "contact_email"),
                    "msg": "value is not a valid string",
                    "input": {"bad": "value"},
                }
            ],
        )

    def _raise_error(*_args, **_kwargs):
        raise _make_error()

    def _fail_model_validate(_cls, *_args, **_kwargs):
        raise _make_error()

    monkeypatch.setattr(schema_module, "coerce_and_fill", _raise_error)
    monkeypatch.setattr(es.NeedAnalysisProfile, "model_validate", classmethod(_fail_model_validate))
    monkeypatch.setattr(es, "repair_profile_payload", lambda *_, **__: None)

    es.ensure_state()

    summary = st.session_state[StateKeys.EXTRACTION_SUMMARY]
    warning = "⚠️ Extracted profile could not be validated – please review the fields manually."
    assert summary["Status"] == warning
    assert summary["Impacted fields"] == "company.contact_email"
    assert st.session_state[StateKeys.STEPPER_WARNING] == warning


def test_ensure_state_defaults_contact_email_when_invalid() -> None:
    st.session_state.clear()
    profile = NeedAnalysisProfile().model_dump()
    profile["company"]["name"] = "ACME GmbH"
    profile["position"]["job_title"] = "Data Scientist"
    profile["company"]["contact_email"] = {"email": "n/a"}

    st.session_state[StateKeys.PROFILE] = profile

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"
    assert result["company"]["contact_email"] == ""


def test_ensure_state_applies_contact_email_default_when_missing() -> None:
    st.session_state.clear()
    profile = NeedAnalysisProfile().model_dump()
    profile["company"].pop("contact_email", None)
    profile["company"]["name"] = "ACME GmbH"
    profile["position"]["job_title"] = "Data Scientist"

    st.session_state[StateKeys.PROFILE] = profile

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["contact_email"] == ""
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"


def test_ensure_state_records_profile_repairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-fixed fields should be captured for UI warnings."""

    st.session_state.clear()
    profile = NeedAnalysisProfile().model_dump()
    profile["company"]["contact_email"] = {"bad": "value"}
    st.session_state[StateKeys.PROFILE] = profile

    monkeypatch.setattr(schema_module, "repair_profile_payload", lambda *_, **__: None)

    es.ensure_state()

    repairs = st.session_state.get(StateKeys.PROFILE_REPAIR_FIELDS)
    assert repairs
    assert "company.contact_email" in repairs["auto_populated"]


def test_ensure_state_ignores_openai_model_secret(monkeypatch) -> None:
    st.session_state.clear()
    monkeypatch.setattr(
        st,
        "secrets",
        {"openai": {"OPENAI_MODEL": "gpt-3.5-turbo"}},
        raising=False,
    )
    importlib.reload(config)
    importlib.reload(es)

    try:
        es.ensure_state()

        assert model_config.OPENAI_MODEL == model_config.PRIMARY_MODEL_DEFAULT
        assert st.session_state["model"] == model_config.PRIMARY_MODEL_DEFAULT
    finally:
        st.session_state.clear()
        monkeypatch.setattr(st, "secrets", {}, raising=False)
        importlib.reload(config)
        importlib.reload(es)


def test_env_openai_override_is_ignored(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    previous_env = os.environ.get("OPENAI_MODEL")

    try:
        monkeypatch.setenv("OPENAI_MODEL", "gpt-3.5-turbo")
        caplog.set_level("WARNING")
        importlib.reload(config)

        assert model_config.OPENAI_MODEL == model_config.PRIMARY_MODEL_DEFAULT
        assert model_config.get_model_for(model_config.ModelTask.DEFAULT) == model_config.PRIMARY_MODEL_DEFAULT
        assert any("Ignoring OPENAI_MODEL" in record.message for record in caplog.records)
    finally:
        if previous_env is None:
            monkeypatch.delenv("OPENAI_MODEL", raising=False)
        else:
            monkeypatch.setenv("OPENAI_MODEL", previous_env)
        importlib.reload(config)


def test_env_default_model_override_is_ignored(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    previous_env = os.environ.get("DEFAULT_MODEL")

    try:
        monkeypatch.setenv("DEFAULT_MODEL", "o3")
        caplog.set_level("WARNING")
        importlib.reload(config)

        assert model_config.DEFAULT_MODEL == model_config.PRIMARY_MODEL_DEFAULT
        assert model_config.OPENAI_MODEL == model_config.PRIMARY_MODEL_DEFAULT
        assert any("DEFAULT_MODEL" in record.message for record in caplog.records)
    finally:
        if previous_env is None:
            monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        else:
            monkeypatch.setenv("DEFAULT_MODEL", previous_env)
        importlib.reload(config)
