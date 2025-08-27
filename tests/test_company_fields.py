import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

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
