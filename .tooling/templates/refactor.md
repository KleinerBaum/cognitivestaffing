# Task: Refactor (Behavior‑Preserving)
## Context
- Commit Message:
{COMMIT_MSG}

- Changed Files:
{FILES}

- Diff (excerpt):


{DIFF}


## Do
1) Vereinheitliche Stil/Architektur (z. B. Pydantic‑Schemas, Funktionen).
2) Erhalte Verhalten (Backwards‑Compat).
3) Entferne Duplication, bessere Namen, klare Module.

## Verify
- Run: ruff && mypy && pytest
- Keine API‑Änderungen ohne Migration Guide.

## Deliverables
- Refactor‑Patch
- Kurze Begründung der Strukturänderungen
