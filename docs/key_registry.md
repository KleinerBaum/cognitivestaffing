# Key Registry & Aliases / Key-Registry & Aliase

This guide explains how canonical schema paths are defined and propagated through
the Cognitive Staffing stack. It complements the CS_SCHEMA_PROPAGATE tasks that
keep schemas, UI bindings, and exports in sync.

## Canonical sources / Kanonische Quellen

- **NeedAnalysisProfile** – the ingestion/export profile that powers
  downstream JSON, session state, and normalisation. The canonical dot-paths are
  available via `core.schema.KEYS_CANONICAL`.
- **RecruitingWizard** – the UI master schema behind the feature flag
  `SCHEMA_WIZARD_V1`. The canonical wizard paths are exposed through
  `core.schema.WIZARD_KEYS_CANONICAL`.

## Alias map / Alias-Tabelle

- `core.schema.ALIASES` captures every legacy key that needs to be migrated to
  a canonical NeedAnalysis path. Use lowercase strings for free-form aliases;
  the alias lookup is case-insensitive.
- When adding a new alias, update tests in `tests/test_aliases.py` so that the
  mapping remains complete and canonical.

## Session state & exports / Session-State & Exporte

- `core.schema.coerce_and_fill()` canonicalises incoming payloads using the
  alias map, filters unknown fields, coerces simple scalars, and validates the
  result against `NeedAnalysisProfile`.
- `state.ensure_state.ensure_state()` always stores a `NeedAnalysisProfile`
  dump in `st.session_state[StateKeys.PROFILE]`; any legacy keys are removed
  during canonicalisation.
- Exports should rely on `core.schema.KEYS_CANONICAL` (NeedAnalysis) or
  `core.schema.WIZARD_KEYS_CANONICAL` (wizard) to avoid hard-coded paths.

## Developer workflow / Entwickler-Workflow

1. Adjust the relevant Pydantic model (`models/need_analysis.py` or
   `core/schema.py`).
2. Regenerate helper artefacts (`scripts/propagate_schema.py`) if the wizard
   schema changes.
3. Update `core.schema.ALIASES` when legacy payloads must continue to work.
4. Extend tests under `tests/test_aliases.py` and affected feature tests.
5. Update docs (`README.md`, `docs/CHANGELOG.md`) with migration notes when the
   key registry changes.

---

**Kurzfassung (DE):** Kanonische NeedAnalysis-Pfade über `KEYS_CANONICAL`,
Wizard-Pfade über `WIZARD_KEYS_CANONICAL`. Legacy-Felder immer in `ALIASES`
abbilden und die Tests aktualisieren, damit Session-State und Exporte keine
veralteten Keys enthalten.
