# Changelog

## Unreleased
- feat: refactor job ad generation to use tone-aware LLM prompts with Markdown fallback
- feat: auto-regenerate job ad and interview outputs when summary follow-up answers are applied
- feat: redesign requirements step with vertical panels and inline AI suggestions
- fix: prevent wizard navigation deadlock when job title is missing
- feat: route CLI file extraction through ingest.extractors for OCR and text support
- fix: show user-friendly labels for missing critical fields
- fix: stack columns and buttons on small screens for mobile usability
- fix: send valid OpenAI tool definitions to avoid missing name errors
- feat: inject required arrays and nullable fields into extraction schema
- fix: map "Einsatzort"/"Branche" cues to location and industry in rule-based parsing
- feat: run extraction through a LangChain validation chain with NeedAnalysisProfile fallbacks
- docs: clarify Responses API migration and removal of Assistants/Threads usage
- docs: add bilingual legal information page including ESCO licensing notice
- fix: show localized warning in requirements step when skill suggestions fail
- fix: infer salary estimate country from primary city/HQ hints when explicit country is missing
