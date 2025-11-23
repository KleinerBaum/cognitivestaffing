# Troubleshooting & Common Issues

## AI output is invalid JSON
- The client validates Responses payloads against JSON schema and retries with exponential backoff.
- If invalid JSON persists, switch to **Precise/Genau** mode to use a higher reasoning model or set `USE_CLASSIC_API=1` to force Chat Completions.
- When everything fails, the app returns an empty profile so the wizard stays usable; check the bilingual warning banners for missing sections.

## OpenAI API errors or rate limits
- Calls automatically retry with backoff. If rate limits continue, reduce batch size, switch to Quick mode, or wait before re-running the step.
- Enable the admin/debug panel to confirm whether Responses or Chat is active. Responses first, then Chat, then static suggestions.

## Responses stream returned no completion
- The client replays the same request without streaming and then falls back to Chat completions. You can also set `USE_CLASSIC_API=1` to stay on Chat for the current session.

## Using the EU endpoint
- Set `OPENAI_API_BASE_URL=https://eu.api.openai.com/v1` either in your shell environment or in `.streamlit/secrets.toml` to keep traffic in-region.

## Handling missing or partial sections
- Critical fields such as company name or role title trigger inline follow-ups and Summary banners. Fill them manually to unblock exports.
- Extraction quality is best for full German or English job descriptions; other languages may yield incomplete or misclassified fields.

## ESCO lookup and caching
- ESCO skill enrichment uses only GET requests to `https://ec.europa.eu/esco/api` and caches results with TTLs. If ESCO is slow, wait for the cache to warm or retry later; the rest of the wizard continues without ESCO data.
