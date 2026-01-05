# Deployment Guide / Deployment-Anleitung

## EN

This release introduces a unified prompt registry (`prompts/registry.yaml`) and
fixed model routing. When deploying the application ensure the following
environment variables are available:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for every LLM request. |
| `VECTOR_STORE_ID` | Optional OpenAI vector store identifier for RAG. |
| `VERBOSITY` | Optional UI verbosity (`low`, `medium`, `high`). |
| `REASONING_EFFORT` | Optional reasoning effort hint (`none`/`minimal` … `high`; `none` is the GPT-5.2 default). |

Model routing defaults to `gpt-4o-mini` (with `gpt-4o`/`gpt-3.5-turbo` fallbacks before any GPT-5.2 escalation) and can be overridden via environment variables or Streamlit secrets such as `OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, and `MEDIUM_REASONING_MODEL`.

The Streamlit Community Cloud deployment reads `infra/deployment.toml`. Set the
`[python]` → `installCommand` entry to `poetry install --no-root` so Streamlit
installs dependencies via the Poetry resolver (which now runs in package-less
mode) and the platform stops warning about competing requirement files.

Deployments without `VECTOR_STORE_ID` will automatically skip Retrieval Augment
ation and show localized hints in the wizard. All LLM calls now load their
system prompts from the registry; remember to redeploy the updated YAML file
alongside the code.

After updating environment variables restart the Streamlit process:

```bash
streamlit run app.py
```

## DE

Mit diesem Release wurde das Prompt-Registry (`prompts/registry.yaml`)
vereinheitlicht und das Modell-Routing festgezogen. Für den Betrieb sind
folgende Umgebungsvariablen relevant:

| Variable | Zweck |
| --- | --- |
| `OPENAI_API_KEY` | Pflichtwert für alle LLM-Anfragen. |
| `VECTOR_STORE_ID` | Optionale OpenAI-Vector-Store-ID für RAG. |
| `VERBOSITY` | Optionale UI-Erklärtiefe (`low`, `medium`, `high`). |
| `REASONING_EFFORT` | Optionale Steuerung der Reasoning-Tiefe (`none`/`minimal` … `high`; `none` ist der GPT-5.2-Standard). |

Das Routing nutzt standardmäßig `gpt-4o-mini` (mit Fallback über `gpt-4o`/`gpt-3.5-turbo`, bevor auf GPT-5.2 eskaliert wird) und kann über Umgebungsvariablen oder Streamlit-Secrets wie `OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL` und `MEDIUM_REASONING_MODEL` angepasst werden.

Das Deployment auf Streamlit Community Cloud nutzt `infra/deployment.toml`.
Setze den Eintrag `[python]` → `installCommand` auf `poetry install --no-root`,
damit Streamlit die Abhängigkeiten über den Poetry-Resolver (jetzt ohne
Packaging-Schritt) installiert und keine Warnung zu konkurrierenden
Requirements-Dateien mehr ausgibt.

Ohne `VECTOR_STORE_ID` läuft die App automatisch ohne Retrieval-Pfad und zeigt
einen lokalisierten Hinweis in der UI. Da alle Prompts nun aus der Registry
geladen werden, muss die aktualisierte `registry.yaml` gemeinsam mit dem Code
ausgerollt werden.

Nach einer Konfigurationsänderung die Streamlit-App neu starten:

```bash
streamlit run app.py
```
