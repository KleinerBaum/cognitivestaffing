import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.rules import apply_rules, build_rule_metadata, PHONE_FIELD
from ingest.types import ContentBlock
from models.need_analysis import Company, NeedAnalysisProfile


def test_company_additional_fields() -> None:
    profile = NeedAnalysisProfile(
        company=Company(
            name="Acme Corp",
            brand_name="Acme Robotics",
            contact_name="Jane Doe",
            contact_email="jane@example.com",
            contact_phone="+49 30 1234567",
        )
    )
    assert profile.company.brand_name == "Acme Robotics"
    assert profile.company.contact_name == "Jane Doe"
    assert profile.company.contact_email == "jane@example.com"
    assert profile.company.contact_phone == "+49 30 1234567"


def test_contact_email_noise_is_trimmed() -> None:
    company = Company(contact_email="  USER@Example.COM   extra text")
    assert company.contact_email == "user@example.com"


def test_contact_email_without_valid_address_is_none() -> None:
    company = Company(contact_email="call us maybe")
    assert company.contact_email is None


def test_contact_email_with_concatenated_string() -> None:
    company = Company(contact_email="m.m@rheinbahn.de.0.0...")
    assert company.contact_email == "m.m@rheinbahn.de"


def test_apply_rules_locks_contact_phone() -> None:
    block = ContentBlock(type="paragraph", text="Telefon: +49 30 1234567")
    matches = apply_rules([block])
    assert PHONE_FIELD in matches
    assert matches[PHONE_FIELD].value == "+49 30 1234567"

    metadata = build_rule_metadata(matches)
    assert PHONE_FIELD in metadata["locked_fields"]
    assert metadata["rules"][PHONE_FIELD]["value"] == "+49 30 1234567"
