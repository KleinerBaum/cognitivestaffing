# Troubleshooting

## Missing API key
Set `OPENAI_API_KEY` via `.env` or Streamlit secrets.

## Non-nano model shows up unexpectedly
- Ensure `STRICT_NANO_ONLY=true`.
- Restart the running process.
- Check env/secrets overrides for model names; strict mode should normalize non-embedding routes back to `gpt-5-nano`.

## Structured output fails
- Confirm Responses payload uses `text.format`.
- Confirm schema contract is strict and serializable.
- Avoid mixing legacy `response_format` guidance into Responses payloads.

## Timeouts and retries
- Increase `OPENAI_REQUEST_TIMEOUT` only if needed.
- Verify retry behavior in logs; fallback behavior should be explicit, not silent.
