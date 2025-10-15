from __future__ import annotations

import pytest

from core import analysis_tools


def test_convert_currency_uses_default_rates() -> None:
    """Currency conversion should rely on bundled FX data when no overrides exist."""

    result = analysis_tools.convert_currency(100, "usd", "eur")

    assert result["success"] is True
    assert result["source_currency"] == "USD"
    assert result["target_currency"] == "EUR"
    assert result["error"] is None
    assert result["converted_amount"] == pytest.approx(92.17, rel=1e-4)
    assert result["exchange_rate"] == pytest.approx(0.921659, rel=1e-6)


def test_normalise_date_honours_custom_formats() -> None:
    """Date normalisation should respect explicit formats and timezone offsets."""

    result = analysis_tools.normalise_date(
        "07-05-2024 18:30 +0200",
        day_first=True,
        formats=["%d-%m-%Y %H:%M %z"],
    )

    assert result["success"] is True
    assert result["iso_date"] == "2024-05-07"
    assert result["iso_datetime"] == "2024-05-07T18:30:00+02:00"
    assert result["timezone"] == "UTC+02:00"
    assert result["utc_offset_minutes"] == 120
    assert result["inferred_format"] == "%d-%m-%Y %H:%M %z"
    assert result["error"] is None

