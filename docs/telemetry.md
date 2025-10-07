# Telemetry & Observability

Cognitive Needs can emit OpenTelemetry traces to capture end-to-end performance
and behaviour of key LLM flows. Tracing is disabled by default. Configure the
service via environment variables before launching the app.

## Configuration

| Variable | Description |
| --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint. Required to enable exports. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Protocol (`http/protobuf` or `grpc`). Defaults to HTTP. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Comma-separated `key=value` headers added to each export. |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Export timeout in seconds. |
| `OTEL_EXPORTER_OTLP_CERTIFICATE` | Path to a CA bundle for TLS validation. |
| `OTEL_EXPORTER_OTLP_INSECURE` | Set to `1` to allow insecure gRPC connections. |
| `OTEL_SERVICE_NAME` | Logical service name reported with spans (`cognitive-needs` by default). |
| `OTEL_TRACES_ENABLED` | Set to `0`/`false` to disable tracing without removing config. |
| `OTEL_TRACES_SAMPLER` | Sampler (`parentbased_traceidratio`, `traceidratio`, `always_on`, `always_off`). |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler argument (e.g. sampling ratio). |

## Instrumented operations

When telemetry is enabled the following spans are emitted:

- OpenAI API calls (`openai.call_chat_api`) including tool execution and token
  usage metadata.
- Structured extraction via `llm.extract_json`.
- Follow-up generation (`llm.generate_followups`).
- Document summarisation, refinement and explanation flows in
  `openai_utils/extraction.py`.

The bootstrap logic lives in `utils/telemetry.py` and is invoked at the start of
`app.py`.
