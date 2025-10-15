"""Utilities for interacting with OpenAI models.

The package is split into focused modules:

* :mod:`openai_utils.api` – client configuration and low-level Responses / Chat
  Completions API helpers.
* :mod:`openai_utils.tools` – functions for building tool specifications.
* :mod:`openai_utils.extraction` – high-level routines for extraction and content
  generation using the API.

Most existing code imports directly from ``openai_utils``; the symbols below are
re-exported for backward compatibility. The Responses client remains the
default, but setting ``USE_CLASSIC_API`` switches helpers to the Chat
Completions interface when required.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Iterable, Iterator

from .api import ChatCallResult as ChatCallResult  # noqa: F401
from .api import call_chat_api as call_chat_api  # noqa: F401
from .api import stream_chat_api as stream_chat_api  # noqa: F401
from .api import ChatStream as ChatStream  # noqa: F401
from .api import client as client  # noqa: F401
from .api import get_client as get_client  # noqa: F401
from .api import model_supports_reasoning as model_supports_reasoning  # noqa: F401
from .api import model_supports_temperature as model_supports_temperature  # noqa: F401
from .tools import build_extraction_tool as build_extraction_tool  # noqa: F401


class _LazyExportList(list[str]):
    """List that loads extraction exports on first access."""

    def __init__(self, initial: Iterable[str]):
        super().__init__(initial)
        self._base_exports = tuple(initial)

    def _ensure_exports(self) -> None:
        _load_extraction_module()

    def __iter__(self) -> Iterator[str]:
        self._ensure_exports()
        return super().__iter__()

    def __contains__(self, item: object) -> bool:
        self._ensure_exports()
        return super().__contains__(item)

    def __len__(self) -> int:
        self._ensure_exports()
        return super().__len__()


__all__: _LazyExportList = _LazyExportList(
    (
        "ChatCallResult",
        "call_chat_api",
        "stream_chat_api",
        "ChatStream",
        "client",
        "get_client",
        "model_supports_reasoning",
        "model_supports_temperature",
        "build_extraction_tool",
    )
)

_extraction_module: ModuleType | None = None
_extraction_exports: tuple[str, ...] | None = None


def _load_extraction_module() -> ModuleType:
    """Import :mod:`openai_utils.extraction` when required."""

    global _extraction_module
    if _extraction_module is None:
        module = importlib.import_module(".extraction", __name__)
        _register_extraction_exports(module)
        _extraction_module = module
    return _extraction_module


def _register_extraction_exports(module: ModuleType) -> None:
    """Update ``__all__`` with exports from the extraction module."""

    global _extraction_exports
    if _extraction_exports is not None:
        return

    exports: Iterable[str]
    if hasattr(module, "__all__"):
        exports = getattr(module, "__all__")
    else:
        exports = [name for name in dir(module) if not name.startswith("_")]

    _extraction_exports = tuple(exports)
    new_exports = [name for name in _extraction_exports if name not in __all__]
    list.extend(__all__, new_exports)


def __getattr__(name: str) -> Any:
    """Lazily expose attributes from :mod:`openai_utils.extraction`."""

    module = _load_extraction_module()
    if hasattr(module, name):
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Return the list of available attributes including lazy exports."""

    names = set(globals())
    names.update(__all__._base_exports)
    if _extraction_exports is not None:
        names.update(_extraction_exports)
    return sorted(names)
