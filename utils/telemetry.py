"""Telemetry bootstrap helpers for OpenTelemetry tracing."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, Mapping, Optional, Sequence

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


@dataclass(frozen=True)
class OtlpConfig:
    """Structured configuration for OTLP exporters."""

    protocol: str
    endpoint: str
    headers: Mapping[str, str] | None = None
    timeout: int | None = None
    certificate_file: str | None = None
    insecure: bool | None = None


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


def _build_otlp_config() -> OtlpConfig | None:
    """Create an OTLP configuration object from environment variables."""

    protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").strip().lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        LOGGER.info("OTLP endpoint not configured; telemetry exporter will not be created")
        return None

    headers = _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS")) or None
    timeout_raw = os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "").strip()
    timeout: Optional[int] = None
    if timeout_raw:
        try:
            timeout = int(float(timeout_raw))
        except ValueError:
            LOGGER.warning("Invalid OTEL_EXPORTER_OTLP_TIMEOUT '%s'; ignoring", timeout_raw)

    certificate_file = os.getenv("OTEL_EXPORTER_OTLP_CERTIFICATE", "").strip() or None
    insecure_flag = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "").strip().lower()
    insecure: bool | None = None
    if insecure_flag in {"1", "true", "yes"}:
        insecure = True

    return OtlpConfig(
        protocol=protocol,
        endpoint=endpoint,
        headers=headers,
        timeout=timeout,
        certificate_file=certificate_file,
        insecure=insecure,
    )


def _format_grpc_headers(headers: Mapping[str, str] | None) -> Sequence[tuple[str, str]] | None:
    """Coerce header mappings to the tuple sequence expected by the gRPC exporter."""

    if not headers:
        return None
    return tuple((key, value) for key, value in headers.items())


def _format_http_headers(headers: Mapping[str, str] | None) -> Dict[str, str] | None:
    """Coerce header mappings to the dictionary format expected by the HTTP exporter."""

    if not headers:
        return None
    return dict(headers)


def _build_grpc_credentials(cert_path: str | None) -> Any | None:
    """Load channel credentials for gRPC exporters when a certificate is configured."""

    if not cert_path:
        return None

    try:
        grpc = import_module("grpc")
    except ImportError:  # pragma: no cover - optional dependency in CI
        LOGGER.warning("gRPC exporter requested custom certificate but grpcio is not installed.")
        return None

    try:
        with open(cert_path, "rb") as cert_file:
            certificate = cert_file.read()
    except OSError as exc:  # pragma: no cover - filesystem edge cases
        LOGGER.warning("Unable to read OTLP certificate '%s': %s", cert_path, exc)
        return None

    ssl_credentials = getattr(grpc, "ssl_channel_credentials", None)
    if ssl_credentials is None:
        LOGGER.warning("grpc.ssl_channel_credentials missing; cannot apply custom certificate.")
        return None

    return ssl_credentials(root_certificates=certificate)


def _create_otlp_exporter() -> Optional[SpanExporter]:
    """Instantiate an OTLP span exporter based on environment settings."""

    config = _build_otlp_config()
    if config is None:
        return None

    if config.protocol in {"grpc", "grpc/protobuf"}:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter

        grpc_headers = _format_grpc_headers(config.headers)
        credentials = _build_grpc_credentials(config.certificate_file)
        return GrpcExporter(
            endpoint=config.endpoint,
            headers=grpc_headers,
            timeout=config.timeout,
            insecure=config.insecure,
            credentials=credentials,
        )

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter

    if config.protocol not in {"http", "http/protobuf"}:
        LOGGER.warning(
            "Unsupported OTEL_EXPORTER_OTLP_PROTOCOL '%s'; falling back to http/protobuf",
            config.protocol,
        )
    http_headers = _format_http_headers(config.headers)
    return HttpExporter(
        endpoint=config.endpoint,
        headers=http_headers,
        timeout=config.timeout,
        certificate_file=config.certificate_file,
    )


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

    if not force:
        existing_provider = trace.get_tracer_provider()
        if getattr(existing_provider, "_cognitive_needs_configured", False):
            LOGGER.debug("Telemetry already initialised; skipping setup")
            return

    service_name = os.getenv("OTEL_SERVICE_NAME", "cognitive-needs")
    resource = Resource.create({"service.name": service_name})
    sampler = _build_sampler()

    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    setattr(provider, "_cognitive_needs_configured", True)
    trace.set_tracer_provider(provider)

    _INITIALISED = True
    LOGGER.info("OpenTelemetry tracing initialised for service '%s'", service_name)


__all__ = ["setup_tracing", "OtlpConfig"]
