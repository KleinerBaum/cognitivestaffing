# Schema versioning and Source-of-Truth (SoT) rules

This repository uses a **central schema registry** (`core/schema_registry.py`) as the single entrypoint for schema/model resolution.

## Canonical registry contract

The registry defines explicitly:

- canonical model per version (`v1`, `v2`),
- canonical JSON schema per version,
- allowed adapter paths (currently `v1 -> v2`).

Do not resolve model/schema pairs ad-hoc in feature code. Use the registry API:

- `get_canonical_model(...)`
- `get_canonical_json_schema(...)`
- `get_adapter(...)` / `adapt_payload(...)`

## Version map

- **v1**
  - model: `models.need_analysis.NeedAnalysisProfile`
  - schema: `schema/need_analysis.schema.json` (builder-backed via `core.schema`)
- **v2**
  - model: `models.need_analysis_v2.NeedAnalysisV2`
  - schema: `schema/need_analysis_v2.schema.json`

## Allowed adapter paths

- `v1 -> v2` via `adapters.v1_to_v2.adapt_v1_to_v2`

Any additional path must be registered centrally and covered by tests before use.

## Layer owners (SoT ownership)

When field keys change, owners must update **their layer** in lockstep:

- **Schema owner**: JSON schema definitions (`schema/*.json`, registry wiring)
- **Model owner**: Pydantic contracts (`models/*`, migration defaults)
- **UI owner**: wizard field usage, required/gating metadata, follow-up routing (`wizard/*`, `wizard_pages/*`, `question_logic.py`, `critical_fields.json`)
- **Export owner**: payload conversion and artifact generation (`generators/*`, `exports/*`, `artifacts/*`)

A schema change is only done when all owners are aligned.

## Mandatory consistency checks

For each supported version:

1. Model field set matches schema field set.
2. Registered adapter output validates against target schema.
3. Export payload generated from adapted profile remains schema-valid.

See `tests/test_schema_registry_consistency.py`.

## Change checklist

- [ ] Register model/schema updates in `core/schema_registry.py`.
- [ ] Keep adapter paths explicit and minimal.
- [ ] Update affected model/schema/UI/export callers.
- [ ] Add or update consistency + adapter tests.
- [ ] Document migration impact here and in changelog when relevant.
