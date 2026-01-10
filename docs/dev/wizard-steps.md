# Wizard steps: adding a new step safely

This guide documents the **single source of truth** for the wizard step registry and the checks you must update so adding a new step is explicit and safe after the registry merge.

## 1) Add a `StepDefinition` in `wizard/step_registry.py`

All wizard steps live in the canonical registry:

- File: `wizard/step_registry.py`
- Collection: `WIZARD_STEPS` (ordered tuple)

Add a new `StepDefinition` entry inside `WIZARD_STEPS` and keep the list in the intended order. The registry order controls navigation, step rendering, and legacy indices.

```python
StepDefinition(
    key="example",
    label=("Beispiel", "Example"),
    panel_header=("Beispiel", "Example"),
    panel_subheader=("Untertitel", "Subheader"),
    panel_intro_variants=(
        ("DE intro", "EN intro"),
        ("DE intro 2", "EN intro 2"),
    ),
    required_fields=(
        "example.section_field",
    ),
    summary_fields=(
        "example.section_field",
    ),
    allow_skip=False,
    renderer=_render_example_step,
    is_active=_example_step_active,
)
```

### Required bilingual strings
The `label`, `panel_header`, `panel_subheader`, and `panel_intro_variants` tuples must include **DE + EN** strings (keep them user-facing and short).

## 2) Define `required_fields` (schema-safe)

`required_fields` are **dot-paths** into the NeedAnalysis schema/model. They must be valid against:

- `schema/need_analysis.schema.json`
- `models/need_analysis.py`
- `core.schema.KEYS_CANONICAL`

Use only canonical paths (e.g., `company.name`, `position.job_title`). A registry integrity test fails if a required field does not exist in the schema.

## 3) Add conditional activation (optional)

To make a step conditional, define a predicate in `wizard/step_registry.py` and pass it via `is_active`:

```python
def _example_step_active(profile: Mapping[str, object], session_state: Mapping[str, object]) -> bool:
    if not _schema_has_section(session_state, "example"):
        return False
    return True
```

The predicate receives the current profile data and session state. Use this to skip steps when a schema section is disabled or when the data context implies the step is irrelevant.

## 4) Implement the renderer in `wizard/steps/<name>_step.py`

Step renderers live in `wizard/steps/`. Add a new module like `wizard/steps/example_step.py` with a public entry point:

```python
def step_example(context: WizardContext) -> None:
    ...
```

Then wire it in `wizard/step_registry.py` with a small wrapper to avoid import cycles:

```python
def _render_example_step(context: WizardContext) -> None:
    from wizard.steps import example_step

    example_step.step_example(context)
```

## 5) Add/extend tests

Update tests to keep registry integrity and metadata aligned:

- `tests/test_step_registry.py`:
  - Ensure step order is explicit.
  - Ensure step keys are unique.
  - Validate that all `required_fields` are valid schema paths.
  - Verify legacy step indices (`wizard/metadata.py` → `PAGE_SECTION_INDEXES`) match the registry.

Run the standard checks (format, lint, type check, tests):

```bash
poetry run ruff format .
poetry run ruff check .
poetry run mypy .
poetry run pytest
```

## Checklist (quick)

- [ ] Add a `StepDefinition` to `wizard/step_registry.py` in the correct order.
- [ ] Ensure all user-facing labels are bilingual (DE/EN).
- [ ] Add valid `required_fields`/`summary_fields` with canonical schema paths.
- [ ] Add a renderer in `wizard/steps/<name>_step.py` and wire it up.
- [ ] (Optional) Add `is_active` predicate for conditional activation.
- [ ] Update tests to guard order, schema paths, and legacy indices.
