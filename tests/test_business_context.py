from __future__ import annotations

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from core.schema import coerce_and_fill
from models.need_analysis import NeedAnalysisProfile
from state.ensure_state import migrate_business_context_state
from wizard.step_registry import get_step


def test_migrate_business_context_state_backfills_org_fields() -> None:
    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = {
        "company": {"name": "Acme", "industry": "FinTech"},
        "department": {"name": "Data Platform"},
        "location": {"primary_city": "Berlin"},
    }

    migrate_business_context_state()

    profile = st.session_state[StateKeys.PROFILE]
    business_context = profile["business_context"]
    assert business_context["org_name"] == "Acme"
    assert business_context["org_unit"] == "Data Platform"
    assert business_context["location"] == "Berlin"
    assert business_context["domain"] == "FinTech"


def test_business_context_domain_is_only_required_field() -> None:
    step = get_step("company")
    assert step is not None
    assert step.required_fields == (str(ProfilePaths.BUSINESS_CONTEXT_DOMAIN),)


def test_business_context_round_trip_persists_values() -> None:
    profile = NeedAnalysisProfile()
    profile.business_context.domain = "FinTech"
    profile.business_context.industry_codes = ["NACE:K64"]
    profile.business_context.org_name = "Acme"

    payload = profile.model_dump(mode="json")
    reloaded = coerce_and_fill(payload)

    assert reloaded.business_context.domain == "FinTech"
    assert reloaded.business_context.industry_codes == ["NACE:K64"]
    assert reloaded.business_context.org_name == "Acme"
