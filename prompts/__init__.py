"""Central registry for prompt templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=4)
def _load_registry_from_path(path: Path, version: str | None) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=512)
def _resolve_prompt_value(path: Path, key: str, locale: str | None, version: str | None) -> Any:
    data: Any = _load_registry_from_path(path, version)
    for part in key.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        else:  # pragma: no cover - defensive branch
            raise KeyError(f"Prompt key '{key}' not found")

    if locale is None:
        return data

    if not isinstance(data, dict):
        raise KeyError(f"Prompt key '{key}' does not support locales")

    normalized = locale.lower()
    if normalized in data:
        return data[normalized]

    short = normalized.split("-")[0]
    if short in data:
        return data[short]

    raise KeyError(f"Prompt key '{key}' missing locale '{locale}'")


_PROMPTS_PATH = Path(__file__).resolve().parent / "registry.yaml"


class PromptRegistry:
    """Load and serve prompt templates from :mod:`prompts/registry.yaml`."""

    def __init__(self, path: Path | None = None, *, version: str | None = None) -> None:
        self._path = path or _PROMPTS_PATH
        self._version = version

    @property
    def path(self) -> Path:
        """Return the path to the registry file."""
        return self._path

    def _load(self) -> dict[str, Any]:
        return _load_registry_from_path(self._path, self._version)

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
            return _resolve_prompt_value(self._path, key, locale, self._version)
        except KeyError:
            if default is not None:
                return default
            raise

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

    def clear_cache(self) -> None:
        """Clear registry caches for this instance and module-level helpers."""

        clear_prompt_cache()


prompt_registry = PromptRegistry()


def clear_prompt_cache() -> None:
    """Clear cached prompt registries and resolved templates."""

    for func in (_load_registry_from_path, _resolve_prompt_value):
        cache_clear = getattr(func, "cache_clear", None)
        if callable(cache_clear):  # pragma: no branch - defensive
            cache_clear()


__all__ = ["PromptRegistry", "clear_prompt_cache", "prompt_registry"]
