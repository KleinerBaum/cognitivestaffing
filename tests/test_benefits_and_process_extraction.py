import pytest

from ingest.heuristics import _extract_benefits_from_text, _extract_hiring_process


@pytest.mark.parametrize(
    "text",
    [
        """
        Unsere Vorteile:
        - Unbefristeter Arbeitsvertrag
        - Flexible Arbeitszeiten
        - Deutschlandticket Job
        - Betriebsrente
        - 30 Tage Urlaub
        """,
        """
        Was wir dir bieten
        • Unbefristeter Arbeitsvertrag
        • Flexible Arbeitszeiten
        • Deutschlandticket Job
        • Betriebsrente
        • 30 Tage Urlaub
        """,
    ],
)
def test_german_benefits_extraction_maps_common_perks(text: str) -> None:
    benefits = _extract_benefits_from_text(text)

    assert "Unbefristeter Arbeitsvertrag" in benefits
    assert any("Flexible Arbeitszeiten" in benefit for benefit in benefits)
    assert any(benefit == "Jobticket" for benefit in benefits)
    assert any("Betriebliche Altersvorsorge" in benefit or "Betriebsrente" in benefit for benefit in benefits)
    assert any("30" in benefit and "Urlaub" in benefit for benefit in benefits)


def test_hiring_process_section_extracts_steps() -> None:
    text = """
    Bewerbungsprozess
    1. Telefoninterview
    2. Fachgespräch
    3. Assessment Center
    4. Finales Gespräch
    """

    steps = _extract_hiring_process(text)

    assert steps is not None
    assert len(steps) >= 4
    assert steps[0].startswith("Telefon")
    assert any("Assessment" in step for step in steps)


def test_inline_hiring_process_chain_splits_steps() -> None:
    text = "Unser Auswahlverfahren: Telefoninterview -> Fachinterview -> Angebot"

    steps = _extract_hiring_process(text)

    assert steps is not None
    assert steps[:3] == ["Telefoninterview", "Fachinterview", "Angebot"]
