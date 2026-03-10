# Error handling and fallback behavior

## Core principles

- Responses is the primary runtime path.
- Structured output contracts in Responses use `text.format`.
- Retry/fallback behavior is explicit and policy-driven (no implicit model-family drift in strict mode).

## Common failures

- Missing API key → fail fast with user-facing guidance.
- Timeout/network errors → surfaced with retry/backoff behavior.
- Schema validation failures → treated as contract issues first (validate schema and payload shape before changing models).
- Unsupported tools in nano runtime → blocked before dispatch.

## Strict nano fallback rules

When `STRICT_NANO_ONLY=true`, non-embedding generation remains on `gpt-5-nano` through candidate selection and fallback normalization.

## Troubleshooting sequence

1. Verify effective config (`STRICT_NANO_ONLY`, `REASONING_EFFORT`, `RESPONSES_ALLOW_TOOLS`).
2. Verify payload shape (`text.format` for Responses structured output).
3. Verify timeout/retry markers in logs.
4. Re-run targeted tests for routing and payload hardening.
