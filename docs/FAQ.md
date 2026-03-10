# FAQ

## Which model is used by default?
`gpt-5-nano` for all non-embedding generation tasks when `STRICT_NANO_ONLY=true`.

## Does Quick vs Precise switch model families?
No. In strict mode both keep the model family on `gpt-5-nano`; only effort/verbosity style differs.

## Why am I seeing schema errors?
Most issues are payload-shape mismatches. Responses structured calls must use `text.format` and valid strict JSON schema.

## Are tools enabled?
Yes, if `RESPONSES_ALLOW_TOOLS=true`. Unsupported nano tool types are explicitly blocked.

## Can I use the EU endpoint?
Yes. Set `OPENAI_BASE_URL=https://eu.api.openai.com/v1`.
