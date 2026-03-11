# Schema versioning and Source-of-Truth (SoT) rules

This repository uses a **central schema registry** (`core/schema_registry.py`) as the only supported entrypoint for schema/model resolution.

## Canonical registry contract

The registry keeps the version contract explicit:

- canonical model per version (`v1`, `v2`),
- canonical JSON schema per version,
- allowed adapter paths (currently only `v1 -> v2`).

Do not resolve model/schema pairs ad-hoc in feature code. Always use the registry API:

- `get_canonical_model(...)`
- `get_canonical_json_schema(...)`
- `get_allowed_adapter_paths(...)`
- `get_adapter(...)` / `adapt_payload(...)`

## Version map

| Version | Canonical model | Canonical JSON schema |
|---|---|---|
| `v1` | `models.need_analysis.NeedAnalysisProfile` | `schema/need_analysis.schema.json` (builder-backed via `core.schema`) |
| `v2` | `models.need_analysis_v2.NeedAnalysisV2` | `schema/need_analysis_v2.schema.json` |

## Allowed adapter paths

| Source | Target | Adapter |
|---|---|---|
| `v1` | `v2` | `adapters.v1_to_v2.adapt_v1_to_v2` |

Any additional path must be registered in `core/schema_registry.py` and covered by tests before use.

## SoT owner matrix by layer

| Layer | Owner responsibility | Primary locations |
|---|---|---|
| Schema | Maintain canonical JSON schemas and registry wiring | `schema/*.json`, `core/schema_registry.py` |
| Model | Keep Pydantic contracts and migration defaults aligned with schema | `models/*`, `schemas.py` |
| UI/Wizard | Keep step field usage, gating, and follow-up ownership aligned with canonical keys | `wizard/*`, `wizard_pages/*`, `question_logic.py`, `critical_fields.json` |
| Export | Ensure export payload mappings and artifact generators match canonical contracts | `generators/*`, `exports/*`, `artifacts/*` |

A schema change is complete only when all layer owners are aligned.

## Mandatory consistency checks

For each supported version:

1. Model field set equals schema field set.
2. Registry exposes only explicit adapter paths.
3. Adapter output validates against target model.
4. Export payload generated from adapted output validates against target schema.

Reference tests: `tests/test_schema_registry_consistency.py`.

## Change checklist

- [ ] Register model/schema updates in `core/schema_registry.py`.
- [ ] Keep adapter paths explicit and minimal.
- [ ] Update affected model/schema/UI/export callers.
- [ ] Add or update consistency + adapter tests.
- [ ] Document migration impact here and in changelog when relevant.
