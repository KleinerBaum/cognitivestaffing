# Changelog

## Unreleased
- feat: redesign requirements step with vertical panels and inline AI suggestions
- fix: prevent wizard navigation deadlock when job title is missing
- feat: route CLI file extraction through ingest.extractors for OCR and text support
- fix: show user-friendly labels for missing critical fields
- fix: stack columns and buttons on small screens for mobile usability
- fix: send valid OpenAI tool definitions to avoid missing name errors
- feat: inject required arrays and nullable fields into extraction schema
- fix: map "Einsatzort"/"Branche" cues to location and industry in rule-based parsing
- feat: run extraction through a LangChain validation chain with NeedAnalysisProfile fallbacks
