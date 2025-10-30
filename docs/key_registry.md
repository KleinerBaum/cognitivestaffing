# Key Registry & Aliases / Key-Registry & Aliase

This guide explains how canonical schema paths are defined and propagated through
the Cognitive Staffing stack. It complements the CS_SCHEMA_PROPAGATE tasks that
keep schemas, UI bindings, and exports in sync.

## Canonical sources / Kanonische Quellen

- **NeedAnalysisProfile** – the ingestion/export profile that powers
  downstream JSON, session state, and normalisation. The canonical dot-paths are
  available via `core.schema.KEYS_CANONICAL`.
- **ProfilePaths** – the enum in `constants/keys.py` that exposes every
  canonical dot-path used by the wizard, exports, tests, and the question logic.
- **Generated wizard metadata** – `components/wizard_schema_types.py` and
  `exports/transform.py` are generated from the canonical field list via
  `python -m scripts.propagate_schema --apply`.

## Alias map / Alias-Tabelle

- `core.schema.ALIASES` keeps ingestion compatible with historic payloads (for
  example `company.logo` → `company.logo_url`). Only extend the map when
  migrating external data—new fields must ship with canonical `ProfilePaths`
  entries from day one.
- The former wizard alias table (`core.schema.WIZARD_ALIASES`) is frozen for
  archived payloads. Do **not** add new entries; the UI reads canonical keys
  directly.

## Session state & exports / Session-State & Exporte

- `core.schema.coerce_and_fill()` canonicalises incoming payloads using the
  alias map, filters unknown fields, coerces simple scalars, and validates the
  result against `NeedAnalysisProfile`.
- `state.ensure_state.ensure_state()` stores a `NeedAnalysisProfile` dump in
  `st.session_state[StateKeys.PROFILE]` on every run; unknown or legacy keys are
  dropped as part of the normalisation.
- Exports and UI summaries should rely on `constants/keys.ProfilePaths`
  (backed by `core.schema.KEYS_CANONICAL`) to avoid hard-coded paths.

## Developer workflow / Entwickler-Workflow

1. Update `models/need_analysis.py::NeedAnalysisProfile` and
   `constants/keys.ProfilePaths` together.
2. Run `python -m scripts.propagate_schema --apply` so generated metadata stays
   in sync.
3. Touch `core.schema.ALIASES` only when you need to migrate external payloads.
4. Extend tests under `tests/test_aliases.py` and the affected feature tests.
5. Update docs (`README.md`, `docs/CHANGELOG.md`) with migration notes when the
   key registry changes.

---

**Kurzfassung (DE):** Kanonische NeedAnalysis-Pfade über `KEYS_CANONICAL`
und `constants.keys.ProfilePaths` nutzen. Neue Felder direkt dort
registrieren, Alt-Inputs nur bei Bedarf über `ALIASES` migrieren und die Tests
entsprechend aktualisieren.
