# Widget Factory Pattern (EN/DE)

## EN

`components.widget_factory` provides schema-bound widget helpers that ensure every
input reads defaults via `wizard._logic.get_value` and writes changes through
`_update_profile`. Use the exported `text_input`, `select`, and `multiselect`
helpers when rendering wizard fields. They accept Streamlit column factories,
placeholders, and localisation-friendly formatters while automatically wiring
`on_change` callbacks to keep summary cards, exports, and follow-up tracking in
sync.

## DE

`components.widget_factory` stellt Schema-gebundene Widget-Helfer bereit, die
Standardwerte über `wizard._logic.get_value` lesen und Änderungen über
`_update_profile` zurückschreiben. Nutze die Funktionen `text_input`, `select`
und `multiselect` für Wizard-Felder. Sie unterstützen Column-Factories,
Platzhalter und lokalisierte Formatter und verdrahten `on_change` automatisch,
damit Zusammenfassungen, Exporte und Follow-ups synchron bleiben.
