# Schema versioning and migrations

This guide explains how the NeedAnalysisProfile schema evolves, how to bump the schema version, and how to migrate older profile exports.

## Current version and history

- **Current schema version:** `1` (see `models/need_analysis.py::CURRENT_SCHEMA_VERSION`).
- **Version history:**
  - **v1:** Initial NeedAnalysisProfile with schema_version support and a no-op migration placeholder.

## When to bump the version

Bump `CURRENT_SCHEMA_VERSION` when a change requires migrating previously exported profiles, including:

- Renaming or removing a field.
- Changing field semantics (e.g., altering types, default values, or accepted enumerations).
- Adding a new field that must be initialized in older payloads (for example, setting a non-empty default or deriving a value from existing fields).

Purely additive optional fields that are safe to leave `None` can stay on the current version, but prefer a bump whenever a migration step is helpful for downstream tools.

## Adding or changing fields

1. Update the Pydantic model in `models/need_analysis.py` and the JSON schema in `schema/need_analysis.schema.json` (keep schema and logic in sync).
2. Propagate the field to UI bindings, exports, and any pipelines that read or write it.
3. If the change needs backfilling, add a migration step (see below) and bump `CURRENT_SCHEMA_VERSION`.
4. Regenerate or adjust fixtures and tests that assert schema structure or versions (for example, `tests/test_schema_migrations.py` and `tests/test_profile_import_export.py`).
5. Document the new version in the history above.

## Writing migrations

- Add a new entry to `core/schema_migrations.py::MIGRATIONS` keyed by the source version. Each function receives a profile payload without `schema_version` and must return an updated payload compatible with `version + 1`.
- Keep migrations idempotent and avoid mutating the input; copy any nested data you modify.
- Use small, focused helpers that only touch the fields introduced or changed in that version.
- Add unit tests that cover migrating from the previous version to the new one, including defaulting and edge cases.

## How `migrate_profile()` works

- Reads `schema_version` from the incoming mapping (defaults to `1` for legacy data) and rejects payloads newer than `CURRENT_SCHEMA_VERSION`.
- Applies migrations sequentially from the detected version up to the current version. If a step is missing from `MIGRATIONS`, a no-op migration runs for that version.
- Merges the migrated payload into a fresh `NeedAnalysisProfile` instance so new fields pick up model defaults and nested dictionaries are preserved.
- Returns a fully populated profile dict with `schema_version` set to `CURRENT_SCHEMA_VERSION`.

## Checklist for schema changes

- [ ] Update the model and JSON schema.
- [ ] Add or update migration steps and bump `CURRENT_SCHEMA_VERSION` if needed.
- [ ] Adjust tests and fixtures to expect the new version.
- [ ] Update this document’s history and references.
