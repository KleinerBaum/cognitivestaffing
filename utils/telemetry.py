"""Telemetry bootstrap helpers for OpenTelemetry tracing."""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)

LOGGER = logging.getLogger("cognitive_needs.telemetry")

_INITIALISED = False


def _parse_headers(raw: str | None) -> Dict[str, str]:
    """Parse comma-separated OTLP headers into a dictionary."""

    headers: Dict[str, str] = {}
    if not raw:
        return headers
    for fragment in raw.split(","):
        if not fragment:
            continue
        if "=" not in fragment:
            continue
        key, value = fragment.split("=", 1)
        key = key.strip()
        if not key:
            continue
        headers[key] = value.strip()
    return headers


def _build_sampler() -> Sampler:
    """Create a sampler based on environment configuration."""

    sampler_name = os.getenv("OTEL_TRACES_SAMPLER", "").strip().lower()
    sampler_arg = os.getenv("OTEL_TRACES_SAMPLER_ARG", "").strip()

    if sampler_name in {"", "parentbased_traceidratio", "parentbased_traceidratio_sampler"}:
        ratio = _coerce_ratio(sampler_arg, default=1.0)
        return ParentBased(TraceIdRatioBased(ratio))
    if sampler_name in {"traceidratio", "traceidratio_sampler"}:
        ratio = _coerce_ratio(sampler_arg, default=1.0)
        return TraceIdRatioBased(ratio)
    if sampler_name in {"always_on", "always_on_sampler"}:
        return ALWAYS_ON
    if sampler_name in {"always_off", "always_off_sampler"}:
        return ALWAYS_OFF

    if sampler_name:
        LOGGER.warning("Unknown OTEL_TRACES_SAMPLER '%s'; defaulting to parentbased_traceidratio", sampler_name)
    return ParentBased(TraceIdRatioBased(1.0))


def _coerce_ratio(raw: str, *, default: float) -> float:
    """Convert ``raw`` to a float ratio within [0.0, 1.0]."""

    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        LOGGER.warning("Invalid OTEL_TRACES_SAMPLER_ARG '%s'; using default %.2f", raw, default)
        return default
    return max(0.0, min(1.0, value))


def _create_otlp_exporter() -> Optional[SpanExporter]:
    """Instantiate an OTLP span exporter based on environment settings."""

    protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").strip().lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None
    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    timeout_raw = os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "").strip()
    certificate_file = os.getenv("OTEL_EXPORTER_OTLP_CERTIFICATE", "").strip() or None

    timeout: Optional[int] = None
    if timeout_raw:
        try:
            timeout = int(float(timeout_raw))
        except ValueError:
            LOGGER.warning("Invalid OTEL_EXPORTER_OTLP_TIMEOUT '%s'; ignoring", timeout_raw)

    exporter_kwargs: Dict[str, object] = {}
    if endpoint:
        exporter_kwargs["endpoint"] = endpoint
    if headers:
        exporter_kwargs["headers"] = headers
    if timeout is not None:
        exporter_kwargs["timeout"] = timeout
    if certificate_file:
        exporter_kwargs["certificate_file"] = certificate_file

    if protocol in {"grpc", "grpc/protobuf"}:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter

        insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "").strip().lower()
        if insecure in {"1", "true", "yes"}:
            exporter_kwargs["insecure"] = True
        return GrpcExporter(**exporter_kwargs)

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter

    if protocol not in {"http", "http/protobuf"}:
        LOGGER.warning(
            "Unsupported OTEL_EXPORTER_OTLP_PROTOCOL '%s'; falling back to http/protobuf",
            protocol,
        )
    return HttpExporter(**exporter_kwargs)


def setup_tracing(*, force: bool = False) -> None:
    """Configure the global tracer provider if telemetry is enabled."""

    global _INITIALISED
    if _INITIALISED and not force:
        return

    enabled_flag = os.getenv("OTEL_TRACES_ENABLED", "1").strip().lower()
    if enabled_flag in {"0", "false", "off"}:
        LOGGER.info("Telemetry disabled via OTEL_TRACES_ENABLED")
        return

    exporter = _create_otlp_exporter()
    if exporter is None:
        LOGGER.debug("No OTLP exporter configured; skipping telemetry bootstrap")
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "cognitive-needs")
    resource = Resource.create({"service.name": service_name})
    sampler = _build_sampler()

    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _INITIALISED = True
    LOGGER.info("OpenTelemetry tracing initialised for service '%s'", service_name)


__all__ = ["setup_tracing"]

