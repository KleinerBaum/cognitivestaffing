"""Tests for telemetry bootstrap helpers."""

from __future__ import annotations

from opentelemetry import trace

from utils import telemetry


def test_setup_tracing_skips_without_endpoint(monkeypatch) -> None:
    """No collector endpoint means tracing is not initialised."""

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_TRACES_ENABLED", "1")
    telemetry._INITIALISED = False

    calls: list[object] = []

    def fake_set_tracer_provider(provider: object) -> None:
        calls.append(provider)

    monkeypatch.setattr(trace, "set_tracer_provider", fake_set_tracer_provider)

    telemetry.setup_tracing(force=True)

    assert calls == []
    assert telemetry._INITIALISED is False
