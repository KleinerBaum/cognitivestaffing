# LLM config and debugging (GPT-5-nano strict mode)

## Effective runtime contract

- Non-embedding tasks run in **strict nano-only** mode (`gpt-5-nano`).
- Runtime is **Responses-first**.
- Structured outputs in Responses use **`text.format`**.
- Default reasoning baseline is **`minimal`**.
- Tool usage can stay enabled (`RESPONSES_ALLOW_TOOLS=true`) with explicit unsupported-tool guards.

## Supported vs unsupported nano tools

Supported for app flows: function calling, structured outputs, file search/web search where enabled by runtime policy.

Blocked for nano runtime: `tool_search`, `computer_use`, `hosted_shell`, `apply_patch`, `skills`.

## Quick verification commands

```bash
ruff check .
pytest -q tests/test_strict_nano_routing.py tests/test_responses_runtime_hardening.py
```

## Troubleshooting

### Missing API key
Set `OPENAI_API_KEY` in `.env` or `.streamlit/secrets.toml`.

### Wrong model appears in logs
1. Confirm `STRICT_NANO_ONLY=true`.
2. Confirm process restart after config change.
3. Check task/env overrides (`MODEL_ROUTING__*`, `OPENAI_MODEL`, `DEFAULT_MODEL`) are being normalized to nano.

### Structured output/schema failure
- Verify call payload uses Responses `text.format` for structured output.
- Validate schema shape (object schema, required/properties alignment).
- Avoid adding legacy `response_format` to Responses payload assembly.

### `response_format` vs `text.format`
- Responses structured output => `text.format`.
- `response_format` is legacy compatibility behavior only.

### Timeout/retry drift
- Verify `OPENAI_REQUEST_TIMEOUT`.
- Inspect logs for explicit retry/fallback markers; no silent endpoint switching should occur when legacy fallback is disabled.
