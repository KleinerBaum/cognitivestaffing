# Troubleshooting

## "missing ScriptRunContext" warnings

**What it means:** Streamlit emits this warning when background threads or async tasks try to
access session- or UI-bound state (e.g. `st.session_state`, widgets, or `st.*` rendering)
outside the main ScriptRunContext.

**What to do:** Keep background tasks limited to pure computation or I/O and pass results
back to the main thread before touching Streamlit state. If you see this warning after a
change, check any new threaded/async code paths for UI access.

## "OTLP endpoint not configured" telemetry message

**What it means:** Telemetry setup is enabled, but `OTEL_EXPORTER_OTLP_ENDPOINT` is not set,
so the exporter is skipped. This is expected in local development when no collector is
configured.

**What to do:**
- For local dev: ignore it, or keep the log level at debug.
- For telemetry: set `OTEL_EXPORTER_OTLP_ENDPOINT` (and optionally protocol/headers) as
  documented in `docs/telemetry.md`.
