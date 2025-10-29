from __future__ import annotations

from pathlib import Path

from ingest.heuristics import apply_basic_fallbacks
from models.need_analysis import NeedAnalysisProfile

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "text" / "rheinbahn_case.txt"


def test_rheinbahn_footer_and_city() -> None:
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    profile = NeedAnalysisProfile()
    metadata: dict[str, object] = {"invalid_fields": []}

    updated = apply_basic_fallbacks(profile, text, metadata=metadata)

    assert updated.location.primary_city == "Düsseldorf"
    assert updated.company.contact_name == "Benjamin Erben"
    assert updated.company.contact_email == "benjamin.erben@rheinbahn.de"
    assert updated.company.contact_phone == "0211 123"
    assert updated.company.website == "https://www.rheinbahn.de/"
    assert updated.company.benefits == [
        "Flexible Arbeitszeiten",
        "Mobiles Arbeiten",
        "Betriebliche Altersvorsorge",
        "Jobticket",
    ]

    field_sources = metadata.get("field_sources")
    assert isinstance(field_sources, dict)
    assert field_sources["location.primary_city"]["rule"] == "city_regex"
    assert field_sources["company.contact_phone"]["rule"] == "footer_contact"
    assert field_sources["company.website"]["rule"] == "footer_contact"
    assert field_sources["company.benefits"]["rule"] == "benefit_lexicon"

    assert "location.primary_city" in metadata.get("high_confidence_fields", [])
    assert "company.contact_phone" in metadata.get("locked_fields", [])
    confidence_map = metadata.get("field_confidence")
    assert isinstance(confidence_map, dict)
    assert confidence_map["company.contact_phone"] >= 0.9
    assert confidence_map["company.benefits"] >= 0.9
    assert updated.location.primary_city != "Flexible Arbeitszeiten"
