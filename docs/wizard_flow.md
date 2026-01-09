# Wizard flow overview

This document explains how the multi-step wizard keeps navigation order, rendering callbacks, and Streamlit session state in sync.

## Page metadata (`wizard_pages`)

* The canonical navigation order lives in `wizard_pages/__init__.py` via the `WIZARD_PAGES` tuple. Each entry is a `WizardPage` dataclass that carries the page key plus localized labels and required/summary field metadata.
* Pages are loaded by filename prefix (for example `01_jobad.py`, `02_company.py`); adjusting the order in `_load_pages()` is enough to reorder the wizard everywhere.

## Required field ownership (`wizard/metadata.py`)

* Required fields must live on the step that actually renders those inputs.
* Prefix ownership is centralized in `PAGE_FOLLOWUP_PREFIXES` (for example `department.*` belongs to the Company step).
* The validation helper `validate_required_fields_by_page` checks that each page's `required_fields` aligns with the prefix map and fails tests if a field is assigned to the wrong step (see `tests/test_required_fields_mapping.py`).

## Rendering callbacks (`wizard.flow`)

* `wizard/flow.py` wires each `WizardPage` key to a `StepRenderer` with the actual Streamlit callback used to render the page.
* Step UIs gradually move into `wizard/steps/` modules (e.g., `company_step.py`, `team_step.py`) so `flow.py` focuses on orchestration and shared helpers instead of per-step layouts.
* `legacy_index` on `StepRenderer` keeps backwards compatibility with older session keys (`StateKeys.STEP` and `_wizard_step_summary`) while navigation relies solely on `WIZARD_PAGES` order.

## Router and navigation (`wizard_router.py`)

* `WizardRouter` receives `pages=WIZARD_PAGES` and derives previous/next links by indexing into that ordered list. No hard-coded page keys or positions remain in the router.
* Summary labels shown in Streamlit state now come directly from `WizardPage.label`, so adding/reordering pages in `wizard_pages/__init__.py` automatically updates the navigation hints.
* The router stores navigation state in `st.session_state["wizard"]` and harmonises query parameters (`?step=<key>`) to keep direct links and reruns aligned with the active page.

## Adding or reordering a page

1. Create or rename the page file under `wizard_pages/` (e.g., `09_new_step.py`) and export `PAGE` as a `WizardPage`.
2. Update the ordered tuple inside `_load_pages()` in `wizard_pages/__init__.py`.
3. Register the render callback in `wizard/flow.py` by adding a `WizardStepDescriptor` for the new key and linking it to a `StepRenderer`.
4. Verify navigation and summary state via `WizardRouter` (link sharing, skip/complete buttons) and run `pytest tests/test_wizard_navigation.py`.

Keeping `WIZARD_PAGES` as the single navigation source ensures the router, sidebar progress, and summary view stay consistent when pages move.
