"""Utilities for interacting with OpenAI models.

The package is split into focused modules:

* :mod:`openai_utils.api` – client configuration and low-level Responses API
  helpers.
* :mod:`openai_utils.tools` – functions for building tool specifications.
* :mod:`openai_utils.extraction` – high-level routines for extraction and content
  generation using the API.

Most existing code imports directly from ``openai_utils``; the symbols below are
re-exported for backward compatibility.
"""

from .api import (
    ChatCallResult,
    call_chat_api,
    get_client,
    client,
    model_supports_temperature,
)
from .tools import build_extraction_tool
from .extraction import *  # noqa: F401,F403
from .extraction import __all__ as _extraction_all

__all__ = [
    "ChatCallResult",
    "call_chat_api",
    "client",
    "get_client",
    "model_supports_temperature",
    "build_extraction_tool",
] + _extraction_all
