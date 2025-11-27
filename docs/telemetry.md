# Telemetry & Observability / Telemetrie & Observability

**EN:** Cognitive Staffing emits OpenTelemetry traces to capture end-to-end performance for LLM-heavy flows. Tracing is disabled by default—enable it via environment variables before launching the app.

**DE:** Cognitive Staffing kann OpenTelemetry-Traces erzeugen, um die End-to-End-Performance LLM-lastiger Abläufe zu messen. Telemetrie ist standardmäßig deaktiviert und wird über Umgebungsvariablen vor dem Start aktiviert.

## Configuration / Konfiguration

| Variable | Description (EN) | Beschreibung (DE) |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint (required to send traces). | OTLP-Collector-Endpunkt (erforderlich für Exporte). |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Protocol (`http/protobuf` or `grpc`, default HTTP). | Protokoll (`http/protobuf` oder `grpc`, Standard HTTP). |
| `OTEL_EXPORTER_OTLP_HEADERS` | Comma-separated `key=value` headers appended to every export. | Kommagetrennte `key=value`-Header für jeden Export. |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Export timeout in seconds. | Export-Timeout in Sekunden. |
| `OTEL_EXPORTER_OTLP_CERTIFICATE` | Optional CA bundle path for TLS validation. | Optionaler Pfad zu einem CA-Bundle für TLS-Validierung. |
| `OTEL_EXPORTER_OTLP_INSECURE` | Set to `1` to allow insecure gRPC connections. | Mit `1` unsichere gRPC-Verbindungen zulassen. |
| `OTEL_SERVICE_NAME` | Logical service name (defaults to `cognitive-needs`). | Logischer Servicename (Standard `cognitive-needs`). |
| `OTEL_TRACES_ENABLED` | Set `0`/`false` to disable tracing without removing config. | Mit `0`/`false` Tracing deaktivieren, ohne Konfig zu löschen. |
| `OTEL_TRACES_SAMPLER` | Sampler (`parentbased_traceidratio`, `traceidratio`, `always_on`, `always_off`). | Sampler (`parentbased_traceidratio`, `traceidratio`, `always_on`, `always_off`). |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler argument (e.g. sampling ratio). | Sampler-Parameter (z. B. Sampling-Ratio). |

## Instrumented operations / Instrumentierte Abläufe

**EN:** With telemetry enabled, spans cover OpenAI calls (`openai.call_chat_api` with tool usage metadata), structured extraction (`llm.extract_json`), follow-up generation (`llm.generate_followups`), and summarisation/refinement flows in `openai_utils/extraction.py`. Bootstrapping lives in `utils/telemetry.py` and runs during `app.py` initialisation.

**DE:** Bei aktivierter Telemetrie erfassen Spans OpenAI-Aufrufe (`openai.call_chat_api` inklusive Tool-Metadaten), strukturierte Extraktion (`llm.extract_json`), Nachfragen-Generierung (`llm.generate_followups`) sowie Zusammenfassungs-/Refinement-Flows in `openai_utils/extraction.py`. Das Bootstrap befindet sich in `utils/telemetry.py` und wird beim Start von `app.py` ausgeführt.

## Session usage schema / Sitzungs-Nutzungs-Schema

```python
{
    "input_tokens": int,
    "output_tokens": int,
    "by_task": {
        "extraction": {"input": int, "output": int},
        # ... additional task buckets ...
    },
}
```

**EN:** Token counters persist in `st.session_state[StateKeys.USAGE]`. Legacy aggregate keys remain for analytics compatibility.

**DE:** Token-Zähler liegen in `st.session_state[StateKeys.USAGE]`. Ältere Aggregat-Schlüssel bleiben für Analytics-kompatible Auswertungen erhalten.

## Budget guard / Budget-Schutz

**EN:** Configure `OPENAI_SESSION_TOKEN_LIMIT` (alias: `OPENAI_TOKEN_BUDGET`) to stop OpenAI calls once the session exceeds the token cap. The flag is stored in `st.session_state[StateKeys.USAGE_BUDGET_EXCEEDED]`, and users see a bilingual warning before further calls are blocked.

**DE:** Setze `OPENAI_SESSION_TOKEN_LIMIT` (Alias: `OPENAI_TOKEN_BUDGET`), um OpenAI-Aufrufe nach Überschreiten des Token-Limits zu stoppen. Der Status liegt in `st.session_state[StateKeys.USAGE_BUDGET_EXCEEDED]`, und die App blendet vor dem Blockieren weiterer Aufrufe einen zweisprachigen Hinweis ein.
