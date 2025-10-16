import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils.contact import infer_contact_name_from_email


def test_infer_contact_name_from_simple_email() -> None:
    assert infer_contact_name_from_email("jane.doe@example.com") == "Jane Doe"


def test_infer_contact_name_handles_hyphen_and_numbers() -> None:
    assert infer_contact_name_from_email("anna-maria.schmidt1985@example.com") == "Anna Maria Schmidt"


def test_infer_contact_name_filters_generic_tokens() -> None:
    assert infer_contact_name_from_email("info@example.com") == ""


def test_infer_contact_name_requires_letters() -> None:
    assert infer_contact_name_from_email("1234@example.com") == ""


def test_infer_contact_name_ignores_short_codes() -> None:
    assert infer_contact_name_from_email("hr@example.com") == ""
