# Task: Bug Fix (Root Cause → Minimal Patch → Tests)
## Context
- Commit Message:
{COMMIT_MSG}

- Changed Files:
{FILES}

- Diff (excerpt):


{DIFF}


## Do
1) Identifiziere die tatsächliche Ursache.
2) Schlage den kleinstmöglichen Fix vor (Codepatch in Blöcken).
3) Ergänze/aktualisiere Tests, die zuvor fehlschlagen.

## Verify
- Run: ruff format && ruff check && mypy && pytest -q -k "<focus>"
- Akzeptanzkriterien:
  - Tests grün
  - Keine API‑Breaking‑Changes ohne Changelog‑Hinweis

## Deliverables
- Patch‑Snippet(s)
- Test‑Snippet(s)
- Changelog‑Notiz (falls nötig)
