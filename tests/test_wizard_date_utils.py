"""Unit tests for ``wizard.date_utils`` helper functions."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import wizard.date_utils as date_utils


class TestParseTimelineRange:
    def test_returns_none_pair_for_missing_value(self) -> None:
        assert date_utils.parse_timeline_range(None) == (None, None)

    def test_parses_start_and_end(self) -> None:
        value = "Timeline: 2024-01-01 → 2024-02-01"
        assert date_utils.parse_timeline_range(value) == (date(2024, 1, 1), date(2024, 2, 1))

    def test_handles_single_date(self) -> None:
        assert date_utils.parse_timeline_range("2024-03-15") == (date(2024, 3, 15), date(2024, 3, 15))


class TestTimelineDefaultRange:
    def test_defaults_to_today_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        today = date(2025, 1, 20)
        monkeypatch.setattr(date_utils, "date", type("_d", (), {"today": staticmethod(lambda: today)}))
        assert date_utils.timeline_default_range(None) == (today, today)

    def test_orders_reversed_dates(self) -> None:
        start, end = date_utils.timeline_default_range("2024-05-02 – 2024-04-01")
        assert start <= end


class TestDefaultDate:
    def test_returns_existing_date(self) -> None:
        today = date.today()
        assert date_utils.default_date(today) == today

    def test_parses_strings(self) -> None:
        assert date_utils.default_date("2024-06-01").isoformat() == "2024-06-01"

    def test_falls_back_to_value(self) -> None:
        fallback = date(2024, 7, 1)
        assert date_utils.default_date("bad", fallback=fallback) == fallback


class TestNormalizeDateSelection:
    def test_returns_pair_for_single_date(self) -> None:
        target = date(2024, 8, 5)
        assert date_utils.normalize_date_selection(target) == (target, target)

    def test_extracts_from_list(self) -> None:
        start = date(2024, 9, 1)
        end = start + timedelta(days=10)
        assert date_utils.normalize_date_selection([start, end]) == (start, end)

    def test_returns_none_for_invalid_input(self) -> None:
        assert date_utils.normalize_date_selection("invalid") == (None, None)
