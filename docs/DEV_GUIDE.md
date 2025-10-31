# Developer Guide / Entwicklerhandbuch

This guide complements the high-level README with step-by-step recipes for
extending the wizard, extraction pipeline, and regression tests. Follow the
`CS_SCHEMA_PROPAGATE` principle: schema ↔ logic ↔ UI ↔ exports must stay in sync.

## Adding a wizard section / Einen Wizard-Abschnitt ergänzen

**EN:**

1. Declare or adjust schema fields in
   `models/need_analysis.py::NeedAnalysisProfile` and refresh generated wizard
   metadata via `python -m scripts.propagate_schema --apply` when field lists
   change.
2. Add matching constants to `constants/keys.py::ProfilePaths` so widgets and
   exports share the same dot-path.
3. Create a step function in `pages/0X_<name>.py` or a helper in
   `wizard/sections/*.py`. Bind widgets with the helpers exposed from `wizard`
   (`profile_text_input`, `profile_selectbox`, …) and resolve defaults via
   `wizard._logic.get_value(ProfilePaths.<FIELD>)`.
4. Register the step inside the navigation order by updating the sequence in
   `pages/__init__.py` and adjust `wizard_router.py` if the entry appears in
   other flows (summary/export routes).
5. Add regression coverage: extend `tests/test_value_binding.py` for bindings and
   place functional tests in `tests/wizard/test_<topic>.py`.
6. Update docs (`README.md`, `docs/CHANGELOG.md`) to highlight the new step and
   mention any contributor-facing implications.

**DE:**

1. Neue Schemafelder in `models/need_analysis.py::NeedAnalysisProfile`
   ergänzen und bei geänderten Feldlisten `python -m scripts.propagate_schema --apply`
   ausführen, um die generierten Wizard-Metadaten zu aktualisieren.
2. Passende Konstanten in `constants/keys.py::ProfilePaths` ergänzen, damit
   Widgets und Exporte denselben Dot-Pfad verwenden.
3. Schritt-Funktion in `pages/0X_<name>.py` oder einem Helper unter
   `wizard/sections/*.py` anlegen. Widgets mit den in `wizard` reexportierten
   Helfern binden (`profile_text_input`, `profile_selectbox`, …) und
   Vorgabewerte über `wizard._logic.get_value(ProfilePaths.<FELD>)` beziehen.
4. Schritt in die Navigationsreihenfolge aufnehmen, indem du die Reihenfolge in
   `pages/__init__.py` anpasst, und `wizard_router.py` prüfen, falls der Eintrag
   in anderen Flows verwendet wird (Zusammenfassung/Export).
5. Regressionstests erweitern: Bindings in `tests/test_value_binding.py`
   ergänzen und Funktionstests unter `tests/wizard/test_<thema>.py` ablegen.
6. Dokumentation (`README.md`, `docs/CHANGELOG.md`) mit dem neuen Schritt und
   den Auswirkungen für Contributor:innen aktualisieren.

## Modifying extraction rules / Extraktionsregeln anpassen

**EN:**

- Regex and keyword heuristics live in `core/rules.py` with helper utilities in
  `ingest/heuristics.py`. Add or adjust patterns there and include descriptive
  identifiers so telemetry can highlight which rule fired.
- When rules feed brand metadata, prefer the dedicated helpers in
  `ingest/branding.py` (`fetch_branding_assets` returns logo URL, claim, brand
  colour and accent palette).
- Extend tests under `tests/ingest/test_rules.py` or
  `tests/ingest/test_branding.py` and add regression fixtures to
  `tests/fixtures/` if you need sample PDFs or HTML snippets.
- Run `pytest tests/ingest -k <pattern>` to scope the suite while iterating.

**DE:**

- Regex- und Keyword-Heuristiken liegen in `core/rules.py`, unterstützende
  Helfer in `ingest/heuristics.py`. Muster dort hinzufügen/anpassen und eine
  sprechende ID vergeben, damit Telemetrie erkennt, welche Regel ausgelöst hat.
- Branding-Metadaten besser über die dedizierten Helfer in
  `ingest/branding.py` einbinden (`fetch_branding_assets` liefert Logo-URL,
  Claim, Markenfarbe und Akzentpalette).
- Tests unter `tests/ingest/test_rules.py` bzw.
  `tests/ingest/test_branding.py` erweitern und bei Bedarf Fixtures in
  `tests/fixtures/` ablegen (PDF-/HTML-Beispiele).
- Während der Arbeit `pytest tests/ingest -k <pattern>` nutzen, um den Testlauf
  zu fokussieren.

## Testing & debugging / Testen & Debugging

**EN:**

- Run `ruff format && ruff check`, `mypy --config-file pyproject.toml`, and
  `pytest -q -m "not integration"` before pushing. The repository enforces
  Python ≥ 3.11 and type hints.
- When iterating on a feature, keep the feedback loop focused to avoid noise
  from unrelated regressions:
  - Run scoped modules, e.g. `pytest -q tests/test_wizard_*.py`, instead of the
    full suite.
  - Use keyword filtering such as `pytest -q -k "wizard or multiselect"` to hit
    all relevant cases in one run.
  - Mark pre-existing out-of-scope failures with
    `@pytest.mark.xfail(reason="<issue link>")` so they surface as expected
    failures until the underlying bug is fixed.
  - Update fixtures or assertions whenever your change intentionally adjusts an
    output, keeping regression expectations aligned with the new behaviour.
- Streamlit logs console output while the app runs. Missing OpenAI keys raise a
  banner defined in `openai_utils/api.py`; when debugging configuration issues
  inspect `st.session_state["system.openai.api_key_missing_alert"]`.
- Enable verbose OpenAI logging by setting `VERBOSITY=high` in the environment
  or Streamlit secrets – prompts will include reasoning hints from
  `openai_utils.api`.

**DE:**

- Vor dem Push `ruff format && ruff check`, `mypy --config-file pyproject.toml`
  sowie `pytest -q -m "not integration"` ausführen. Das Repo verlangt Python ≥
  3.11 und Typ-Hints.
- Während der Entwicklung die Feedback-Schleife fokussiert halten, um
  Fehlermeldungen aus anderen Bereichen zu vermeiden:
  - Gezielt Module laufen lassen, z. B. `pytest -q tests/test_wizard_*.py`,
    statt direkt die gesamte Suite auszuführen.
  - Mit Stichwortfiltern wie `pytest -q -k "wizard or multiselect"` alle
    relevanten Fälle in einem Lauf abdecken.
  - Vorhandene, nicht zum aktuellen Task gehörende Fehler mit
    `@pytest.mark.xfail(reason="<issue link>")` kennzeichnen, damit sie als
    erwartete Fehlschläge sichtbar bleiben, bis der Ursprung behoben ist.
  - Fixtures oder Assertions anpassen, sobald sich Ergebnisse durch deine
    Änderung absichtlich ändern, damit die Regressionserwartungen zur neuen
    Logik passen.
- Streamlit protokolliert Konsolenausgaben während der Laufzeit. Fehlende
  OpenAI-Schlüssel lösen das Banner aus `openai_utils/api.py` aus; bei
  Konfigurationsproblemen `st.session_state["system.openai.api_key_missing_alert"]`
  prüfen.
- Setze `VERBOSITY=high` in der Umgebung oder in den Streamlit-Secrets, um
  ausführlichere OpenAI-Logs zu erhalten – die Prompts enthalten dann zusätzliche
  Reasoning-Hinweise aus `openai_utils.api`.
