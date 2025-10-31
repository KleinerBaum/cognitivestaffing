from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.propagate import run_propagation


pytestmark = pytest.mark.integration


def test_no_drift() -> None:
    repo_root = PROJECT_ROOT

    result = run_propagation(repo_root, apply=False, mode="test")
    assert not result.has_drift, result.report

    completed = subprocess.run(
        [sys.executable, "scripts/propagate_schema.py"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    report_path = repo_root / "artifacts" / "schema_report.md"
    assert report_path.exists(), "schema report missing after propagation run"
