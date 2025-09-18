"""Tests for phase participant filtering in the wizard."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wizard import _filter_existing_participants  # noqa: E402


def test_filter_existing_participants_preserves_known_entries() -> None:
    """Previously saved participants should remain when still available."""

    participants = ["Alice", "Bob"]
    stakeholder_names = ["Alice", "Bob", "Charlie"]

    assert (
        _filter_existing_participants(participants, stakeholder_names) == participants
    )


def test_filter_existing_participants_removes_unknown_entries() -> None:
    """Orphaned participant selections must be ignored."""

    participants = ["Alice", "Bob", "Zoe"]
    stakeholder_names = ["Alice", "Charlie"]

    assert _filter_existing_participants(participants, stakeholder_names) == ["Alice"]
