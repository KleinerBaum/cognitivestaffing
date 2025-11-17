"""Central registry for prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROMPTS_PATH = Path(__file__).resolve().parent / "registry.yaml"


class PromptRegistry:
    """Load and serve prompt templates from :mod:`prompts/registry.yaml`."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _PROMPTS_PATH
        self._cache: dict[str, Any] | None = None

    @property
    def path(self) -> Path:
        """Return the path to the registry file."""
        return self._path

    def _load(self) -> dict[str, Any]:
        if self._cache is None:
            with self._path.open("r", encoding="utf-8") as handle:
                self._cache = yaml.safe_load(handle)
        return self._cache

    def get_raw(self, key: str) -> Any:
        """Return the raw registry entry for ``key`` using dot traversal."""
        data: Any = self._load()
        for part in key.split("."):
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:  # pragma: no cover - defensive branch
                raise KeyError(f"Prompt key '{key}' not found")
        return data

    def get(
        self,
        key: str,
        *,
        locale: str | None = None,
        default: Any | None = None,
    ) -> Any:
        """Return the prompt entry identified by ``key``.

        Args:
            key: Dot-separated path inside the registry hierarchy.
            locale: Optional locale code. When provided, the method searches for
                locale-specific variants first (e.g. ``de-DE`` -> ``de``).
            default: Optional default value when the key or locale-specific
                variant is missing.
        """

        try:
            value = self.get_raw(key)
        except KeyError:
            if default is not None:
                return default
            raise

        if locale is None:
            return value

        if not isinstance(value, dict):
            raise KeyError(f"Prompt key '{key}' does not support locales")

        normalized = locale.lower()
        if normalized in value:
            return value[normalized]

        short = normalized.split("-")[0]
        if short in value:
            return value[short]

        if default is not None:
            return default

        raise KeyError(f"Prompt key '{key}' missing locale '{locale}'")

    def format(
        self,
        key: str,
        *,
        locale: str | None = None,
        default: str | None = None,
        **params: Any,
    ) -> str:
        """Return a formatted template string identified by ``key``."""

        template = self.get(key, locale=locale, default=default)
        if template is None:
            raise KeyError(f"Prompt key '{key}' resolved to None")
        if not isinstance(template, str):
            raise TypeError(f"Prompt key '{key}' must resolve to a string")
        return template.format(**params)


prompt_registry = PromptRegistry()

__all__ = ["PromptRegistry", "prompt_registry"]
