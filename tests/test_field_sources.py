import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from constants.keys import StateKeys
from ingest.types import ContentBlock
from wizard import _field_lock_config, _summary_source_icon_html


def setup_function() -> None:
    st.session_state.clear()
    st.session_state.lang = "en"


def test_field_lock_config_includes_rule_source_tooltip() -> None:
    """Rule-based matches should expose their source descriptor."""

    st.session_state[StateKeys.PROFILE_METADATA] = {
        "rules": {
            "company.contact_phone": {
                "confidence": 0.93,
                "source_text": "Telefon: +49 30 1234567",
                "block_type": "paragraph",
                "document_source": "https://example.com/job",
                "page": 3,
            }
        },
        "locked_fields": [],
        "high_confidence_fields": [],
    }
    st.session_state[StateKeys.RAW_BLOCKS] = [
        ContentBlock(
            type="paragraph",
            text="Telefon: +49 30 1234567",
            metadata={"page": 3},
        )
    ]

    config = _field_lock_config("company.contact_phone", "Phone")

    assert "ℹ️" in config["label"]
    help_text = config.get("help_text", "")
    assert "Job ad paragraph" in help_text
    assert "Confidence: 93%" in help_text
    assert "Telefon: +49 30 1234567" in help_text


def test_field_lock_config_marks_llm_inference() -> None:
    """LLM-derived values should be flagged as inferred."""

    st.session_state[StateKeys.PROFILE_METADATA] = {
        "rules": {
            "company.name": {
                "rule": "llm.extract_json",
                "value": "Acme Corp",
                "inferred": True,
                "source_kind": "job_posting",
                "document_source": "https://example.com/job",
                "source_text": "Acme Corp",
            }
        },
        "locked_fields": [],
        "high_confidence_fields": [],
        "llm_fields": ["company.name"],
    }

    config = _field_lock_config("company.name", "Company name")

    help_text = config.get("help_text", "")
    assert "ℹ️" in config["label"]
    assert "Inferred by AI from Job ad snippet" in help_text
    assert "Source: Job ad snippet" in help_text


def test_summary_source_icon_uses_tooltip() -> None:
    """Summary tables should expose the same tooltip HTML."""

    st.session_state[StateKeys.PROFILE_METADATA] = {
        "rules": {
            "company.contact_phone": {
                "confidence": 0.87,
                "source_text": "Phone: +49 30 1234567",
                "block_type": "paragraph",
                "document_source": "https://example.com/job",
            }
        }
    }

    html = _summary_source_icon_html("company.contact_phone")
    assert "ℹ️" in html
    assert "title=" in html
    assert "Job ad paragraph" in html
