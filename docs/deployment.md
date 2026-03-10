# Deployment

## Required environment

- Python >= 3.11
- `OPENAI_API_KEY`
- Streamlit-compatible deployment target

## Recommended OpenAI config

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_REQUEST_TIMEOUT=120
STRICT_NANO_ONLY=true
OPENAI_MODEL=gpt-5-nano
DEFAULT_MODEL=gpt-5-nano
LIGHTWEIGHT_MODEL=gpt-5-nano
MEDIUM_REASONING_MODEL=gpt-5-nano
HIGH_REASONING_MODEL=gpt-5-nano
REASONING_EFFORT=minimal
VERBOSITY=low
RESPONSES_ALLOW_TOOLS=true
```

Optional EU endpoint:

```env
OPENAI_BASE_URL=https://eu.api.openai.com/v1
```

## Deployment checks

- App boot succeeds.
- Non-embedding calls resolve to `gpt-5-nano`.
- Structured calls succeed using Responses `text.format`.
- Wizard extraction, follow-ups, generation, and exports run end-to-end.
