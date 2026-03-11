from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys
from core.confidence import ConfidenceMeta
from state.ai_contributions import get_profile_metadata, set_profile_metadata


def setup_function() -> None:
    st.session_state.clear()


def test_get_profile_metadata_adapts_legacy_payload() -> None:
    st.session_state[StateKeys.PROFILE_METADATA] = {
        "field_confidence": {"company.name": {"score": 0.9, "source": "llm"}},
        "rules": {"company.name": {"source_text": "ACME Corp", "block_type": "paragraph"}},
        "locked_fields": ["company.name"],
        "high_confidence_fields": ["company.name"],
        "llm_recovery": {"invalid_json": True, "repaired": True},
    }

    metadata = get_profile_metadata()

    assert metadata.confidence["company.name"].score == 0.9
    assert metadata.evidence["company.name"].source_text == "ACME Corp"
    assert "company.name" in metadata.locking.locked_fields
    assert metadata.recovery.invalid_json is True


def test_set_profile_metadata_persists_legacy_projection() -> None:
    metadata = get_profile_metadata()
    metadata.locking.locked_fields = ["location.country"]
    metadata.confidence["location.country"] = ConfidenceMeta(
        source="heuristic",
        score=0.4,
        tier="ai_assisted",
    )
    set_profile_metadata(metadata)

    persisted = st.session_state[StateKeys.PROFILE_METADATA]
    assert persisted["version"] == 1
    assert persisted["field_confidence"]["location.country"]["score"] == 0.4
    assert persisted["locked_fields"] == ["location.country"]
