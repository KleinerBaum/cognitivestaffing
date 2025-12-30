# Developer Guide / Entwicklerhandbuch

This guide complements the high-level README with step-by-step recipes for
extending the wizard, extraction pipeline, and regression tests. Follow the
`CS_SCHEMA_PROPAGATE` principle: schema ↔ logic ↔ UI ↔ exports must stay in sync.

## Model defaults & overrides / Modell-Defaults & Overrides

**EN:**

- Model selection is fixed to `gpt-5.1-mini` inside `config/models.py` with automatic escalation to GPT-5.2 for heavier or resilience-driven tasks. There is no Quick/Precise toggle or UI dropdown; routing stays internal for consistent performance and cost control.
- Legacy overrides such as `OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, and `REASONING_MODEL` are deprecated and cleaned up by `python -m cli.reset_api_flags`; adjust model names only in `config/models.py`.
- Responses API remains the default path; toggle with `USE_RESPONSES_API`/`USE_CLASSIC_API` as needed. Keep tool allowances (`RESPONSES_ALLOW_TOOLS`) in sync with tenant capabilities.

**DE:**

- Die Modellauswahl ist in `config/models.py` fest auf `gpt-5.1-mini` eingestellt und hebt automatisch auf GPT-5.2 an, wenn mehr Reasoning oder Ausfallsicherheit nötig ist. Es gibt keinen Schnell/Quick- bzw. Genau/Precise-Schalter und kein UI-Dropdown mehr; das Routing läuft intern, um Leistung und Kosten stabil zu halten.
- Veraltete Overrides wie `OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL` und `REASONING_MODEL` sind abgeschaltet und werden durch `python -m cli.reset_api_flags` bereinigt; Modellnamen werden nur in `config/models.py` angepasst.
- Standard ist weiterhin die Responses API; bei Bedarf mit `USE_RESPONSES_API`/`USE_CLASSIC_API` umschalten und Tool-Freigaben (`RESPONSES_ALLOW_TOOLS`) passend zur Mandantenfähigkeit setzen.

## Prompt generator hook / Prompt-Generator-Hook

**EN:**

- The repository ships a pre-commit hook under `.git-hooks/pre-commit` that
  turns staged diffs into Codex-ready prompts via `.tooling/promptgen.py` and
  saves them to `.tooling/out_prompts/`.
- Enable it once per clone with `git config core.hooksPath .git-hooks` and make
  sure Python 3.11+ is available; the hook uses `git diff --cached` so only
  staged changes are captured.
- Prompt templates live in `.tooling/templates/{feature,bugfix,refactor}.md`;
  adjust them if the prompting rules evolve. Generated JSON files are ignored
  by git.

**DE:**

- Das Repo enthält einen Pre-Commit-Hook unter `.git-hooks/pre-commit`, der
  gestagte Diffs per `.tooling/promptgen.py` in Codex-taugliche Prompts
  umwandelt und in `.tooling/out_prompts/` ablegt.
- Aktiviere ihn einmalig pro Clone mit `git config core.hooksPath .git-hooks`
  und stelle sicher, dass Python ≥ 3.11 verfügbar ist; der Hook nutzt `git diff
  --cached`, daher landen nur gestagte Änderungen im Prompt.
- Die Prompt-Vorlagen liegen in `.tooling/templates/{feature,bugfix,refactor}.md`
  und können bei geänderten Prompting-Vorgaben angepasst werden. Generierte JSONs
  sind git-ignored.

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

**EN:** When wiring UI toggles that mirror session-state flags (for example the
strict JSON checkbox), reuse the canonical state key as the widget key so
Streamlit reruns do not create duplicate entries that trigger immutable-key
errors.

**DE:** Bei UI-Schaltern, die Session-Flags spiegeln (z. B. Strict-JSON-Checkbox),
immer den kanonischen Session-Key als Widget-Key verwenden, damit Streamlit bei
Reruns keine doppelten Einträge erzeugt und Fehler zu unveränderlichen Keys
vermeidet.

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

### Follow-up widgets / Follow-up-Widgets

**EN:** Inline follow-up prompts store both the visible answer and their focus
state under `st.session_state[f"fu_{<schema_path>}"]`; the widget factory in
`wizard/sections/followups.py::_render_followup_question` initialises these keys
the moment a question card is rendered and keeps any pre-filled profile values
in sync with the sidebar list. When a value is applied (manual input, suggestion
chip, or the summary form) call `_sync_followup_completion` so the helper removes
the `fu_*` entries, updates `StateKeys.FOLLOWUPS`, and mirrors the completion to
the sidebar and `followups_answered` metadata. Clearing the key is also required
whenever a follow-up disappears because its schema path was dropped or reset;
otherwise the sidebar will continue to highlight stale cards. See
`tests/test_followup_inline.py` for regression coverage.

**EN:** Treat widget return values (or explicit `value=` defaults) as the only
source of truth for follow-up answers. Wire new cards through
`_update_profile(..., session_value=<widget_value>, sync_widget_state=...)` and
avoid mutating canonical `st.session_state["<field>"]` entries after widgets
have mounted – direct session-state edits trigger Streamlit's immutable-key
errors and desynchronise the sidebar/summary badges.

**DE:** Inline-Follow-ups speichern sowohl den sichtbaren Wert als auch ihren
Fokusstatus in `st.session_state[f"fu_{<schema_path>}"]`; die Widget-Factory in
`wizard/sections/followups.py::_render_followup_question` legt die Keys beim
Rendern einer Frage an und hält bereits befüllte Profilwerte synchron zur
Sidebar-Liste. Sobald eine Antwort übernommen wird (manuelle Eingabe,
Vorschlags-Chip oder Summary-Formular), `_sync_followup_completion` aufrufen: Der
Helper entfernt die `fu_*`-Einträge, aktualisiert `StateKeys.FOLLOWUPS` und
spiegelt die Erledigung an die Sidebar sowie die `followups_answered`-Metadaten.
Die Keys müssen ebenfalls gelöscht werden, wenn ein Follow-up entfällt, weil der
Schema-Pfad entfernt oder zurückgesetzt wurde – andernfalls hebt die Sidebar
weiterhin veraltete Karten hervor. Details deckt `tests/test_followup_inline.py`
ab.

**DE:** Behandle Widget-Rückgabewerte (oder explizite `value=`-Defaults) als
einzige Quelle der Wahrheit für Follow-up-Antworten. Neue Karten immer über
`_update_profile(..., session_value=<widget_value>, sync_widget_state=...)`
verdrahten und keine kanonischen `st.session_state["<feld>"]`-Einträge nach dem
Widget-Mount verändern – direkte Session-Edits erzeugen Streamlit-Fehler zu
unveränderlichen Keys und bringen Sidebar- bzw. Summary-Badges aus dem Takt.

**EN:** When introducing a new follow-up rule, keep these touch points in sync:

1. Add the schema path to `critical_fields.json` + `question_logic.CRITICAL_FIELDS`
   so the routing logic knows the field is required.
2. Register bilingual prompt copy, description, and suggestions in
   `wizard/sections/followups.py::CRITICAL_FIELD_PROMPTS`. Optional keys such as
   `priority` or `ui_variant` ("info"/"warning") control styling inside the card.
3. Map the field to the correct section and page by updating
   `wizard.metadata.PAGE_FOLLOWUP_PREFIXES` / `FIELD_SECTION_MAP`; this keeps
   `_render_followups_for_step()` aligned with the sidebar gating plus
   `get_missing_critical_fields()`.
4. Extend `tests/test_followup_inline.py` (rendering) and
   `tests/test_ask_followups.py` (LLM payload shape) whenever you change the
   follow-up payload.

**DE:** Beim Einführen neuer Follow-up-Regeln gelten folgende Schritte:

1. Schema-Pfad in `critical_fields.json` und `question_logic.CRITICAL_FIELDS`
   ergänzen, damit die Routing-Logik das Feld als Pflichtfeld behandelt.
2. Zweisprachige Prompt-Texte, Beschreibung und Vorschläge in
   `wizard/sections/followups.py::CRITICAL_FIELD_PROMPTS` hinterlegen. Optionale
   Keys wie `priority` oder `ui_variant` ("info"/"warning") steuern die Darstellung
   innerhalb der Karte.
3. Feld der richtigen Sektion bzw. Seite zuordnen, indem
   `wizard.metadata.PAGE_FOLLOWUP_PREFIXES` / `FIELD_SECTION_MAP` angepasst werden;
   dadurch bleiben `_render_followups_for_step()` sowie
   `get_missing_critical_fields()` mit der Sidebar-Sperre synchron.
4. `tests/test_followup_inline.py` (Rendering) und `tests/test_ask_followups.py`
   (LLM-Payload) erweitern, sobald sich Follow-up-Payloads ändern.

## Modifying extraction rules / Extraktionsregeln anpassen

**EN:**

- Regex and keyword heuristics live in `core/rules.py` with helper utilities in
  `ingest/heuristics.py`. Add or adjust patterns there and include descriptive
  identifiers so telemetry can highlight which rule fired.
- Section cues for responsibilities/requirements/benefits/process live in
  `llm/prompts.py::_SECTION_PATTERNS`; extend those tuples when adding new
  headings or languages so the extractor stops at benefit blocks (e.g., "Wir
  bieten") and captures hiring steps (e.g., "Bewerbungsprozess") without
  mixing tasks and requirements.
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
- Abschnitts-Hinweise für Verantwortlichkeiten/Anforderungen/Benefits/Process
  stehen in `llm/prompts.py::_SECTION_PATTERNS`; erweitere diese Tupel bei
  neuen Überschriften oder Sprachen, damit der Extraktor an Benefit-Blöcken
  (z. B. „Wir bieten“) stoppt, Hiring-Schritte (z. B. „Bewerbungsprozess“)
  erkennt und Aufgaben von Anforderungen getrennt bleiben.
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

## LLM feature flags / LLM-Feature-Flags

**EN:**

- `USE_RESPONSES_API` stays enabled by default so structured calls keep using
  the OpenAI Responses API with strict JSON schemas and streaming support.
- `USE_CLASSIC_API` can still be forced (set to `1`) for debugging legacy
  behaviour; the client cascades through Responses → Chat → static fallbacks on
  failures.
- `RESPONSES_ALLOW_TOOLS` defaults to `0` because the 2025 Responses rollout
  blocks tool payloads. Only flip it to `1` when your OpenAI account is
  allowlisted for tool-capable Responses calls; otherwise the SDK will downshift
  to the chat backend whenever a prompt requires tools (analysis helpers,
  function calling, etc.).

**DE:**

- `USE_RESPONSES_API` bleibt standardmäßig aktiviert, damit strukturierte
  Aufrufe weiterhin die OpenAI-Responses-API mit striktem JSON-Schema und
  Streaming-Unterstützung nutzen.
- `USE_CLASSIC_API` lässt sich (Wert `1`) weiterhin erzwingen, um Legacy-
  Verhalten zu debuggen; der Client fällt bei Fehlern über Responses → Chat →
  statische Fallbacks zurück.
- `RESPONSES_ALLOW_TOOLS` steht standardmäßig auf `0`, weil der Responses-
  Rollout 2025 Tool-Payloads blockiert. Aktiviere den Wert nur, wenn dein
  OpenAI-Account für toolfähige Responses-Aufrufe freigeschaltet ist; andernfalls
  wechselt das SDK automatisch auf das Chat-Backend, sobald ein Prompt Tools
  (Analyse-Helfer, Function Calling usw.) benötigt.
