from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from constants.keys import StateKeys, UIKeys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_esco_occupation_selector_does_not_mutate_widget_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure the ESCO selector renders without widget-state mutation errors."""

    monkeypatch.setattr("wizard.flow._refresh_esco_skills", lambda *_, **__: None)

    app_file = tmp_path / "esco_app.py"
    app_file.write_text(
        """
import streamlit as st
from constants.keys import StateKeys, UIKeys
from wizard.flow import _render_esco_occupation_selector

options = [
    {
        "uri": "http://example.com/esco/occupation/1",
        "preferredLabel": "Data Scientist",
        "group": "ICT",
    },
    {
        "uri": "http://example.com/esco/occupation/2",
        "preferredLabel": "ML Engineer",
        "group": "ICT",
    },
]

st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = options
st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = [options[0]["uri"]]

_render_esco_occupation_selector({"occupation_uri": options[0]["uri"]})
""".lstrip(),
        encoding="utf-8",
    )

    app = AppTest.from_file(str(app_file))
    app.run(timeout=30)

    widget_state = app.session_state[UIKeys.POSITION_ESCO_OCCUPATION_WIDGET]

    assert isinstance(widget_state, list)
    assert len(app.multiselect) == 1
