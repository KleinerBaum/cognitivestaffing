# Dynamic, Data-Driven Wizard Roadmap

This document outlines the conceptual checklist and task list for transitioning the NeedAnalysis-driven wizard to a dynamic, signal-aware flow. The detailed, Codex-optimized tasks live in `docs/dynamic_flow_tasks.json`.

## Compact Conceptual Checklist
1. Unify schemas and critical fields into a single source of truth that can drive extraction, UI rendering, and exports.
2. Extend the NeedAnalysis schema with conditional metadata so detected signals map to follow-up question blocks.
3. Build robust extraction pipelines that pull competencies, signals, and timing/location context directly from job texts.
4. Orchestrate a dynamic wizard engine that renders only relevant questions based on extracted signals and existing profile data.
5. Keep exports, summaries, and AI assistants aligned with the dynamic profile state, ensuring bilingual copy and schema propagation.
6. Instrument validation, telemetry, and recovery flows (timeouts, retries, caching) to keep the experience reliable.
7. Harden the rollout with tests, documentation, and migration notes covering schema, logic, and UI changes.
