"""Infrastructure helpers for Cognitive Staffing deployments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - Python <3.11 fallback
    raise RuntimeError("Python 3.11 or newer is required to load deployment config") from exc


_DEFAULT_PYTHON_VERSION = "3.11"
_DEFAULT_REQUIREMENTS_FILE = "requirements.txt"


@dataclass(frozen=True, slots=True)
class DeploymentConfig:
    """Static deployment configuration for Streamlit/community hosting."""

    python_version: str = _DEFAULT_PYTHON_VERSION
    requirements_file: str = _DEFAULT_REQUIREMENTS_FILE


def _load_toml(path: Path) -> dict[str, Any]:
    """Return the parsed TOML payload for ``path`` if available."""

    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_deployment_config(path: str | Path | None = None) -> DeploymentConfig:
    """Load deployment defaults from ``infra/deployment.toml``.

    Args:
        path: Optional override pointing to an alternative config file.

    Returns:
        Parsed :class:`DeploymentConfig` with sane defaults when keys are missing.
    """

    target = Path(path) if path is not None else Path(__file__).with_name("deployment.toml")
    payload = _load_toml(target)

    python_block = payload.get("python") if isinstance(payload, dict) else {}
    if not isinstance(python_block, dict):
        python_block = {}

    version_raw = python_block.get("version") or python_block.get("python_version")
    python_version = str(version_raw).strip() if isinstance(version_raw, str) else None
    if not python_version:
        python_version = _DEFAULT_PYTHON_VERSION

    requirements_raw = (
        python_block.get("requirements")
        or python_block.get("requirements_file")
        or python_block.get("requirementsFile")
    )
    requirements_file = str(requirements_raw).strip() if isinstance(requirements_raw, str) else None
    if not requirements_file:
        requirements_file = _DEFAULT_REQUIREMENTS_FILE

    return DeploymentConfig(python_version=python_version, requirements_file=requirements_file)


DEPLOYMENT_CONFIG = load_deployment_config()


__all__ = ["DeploymentConfig", "DEPLOYMENT_CONFIG", "load_deployment_config"]
