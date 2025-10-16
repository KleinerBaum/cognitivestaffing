"""Typed bridge for lazily importing OpenAI helpers used by the wizard.

This module exposes Protocol-based callables mirroring the public helpers that
the wizard relies on while resolving the actual implementations lazily via
``importlib``. By loading ``openai_utils`` inside helper functions instead of at
module import time, static type checkers such as MyPy treat the dependency as an
``Any``-typed module, preventing deep traversal of the legacy package during
scoped checks.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Mapping, Protocol, Sequence, Tuple, cast


class CallChatApi(Protocol):
    """Callable signature for ``openai_utils.call_chat_api``."""

    def __call__(self, messages: Sequence[Mapping[str, Any]] | Any, /, **kwargs: Any) -> Any:
        ...


class BuildFileSearchTool(Protocol):
    """Callable signature for ``openai_utils.tools.build_file_search_tool``."""

    def __call__(self, vector_store_ids: Sequence[str] | str, /, **kwargs: Any) -> dict[str, Any]:
        ...


class GenerateJobAd(Protocol):
    """Callable signature for ``openai_utils.generate_job_ad``."""

    def __call__(
        self,
        session_data: Mapping[str, Any],
        selected_fields: Sequence[str],
        /,
        *,
        target_audience: str,
        manual_sections: Sequence[Mapping[str, str]] | None = None,
        style_reference: str | None = None,
        tone: str | None = None,
        lang: str | None = None,
        model: str | None = None,
        selected_values: Mapping[str, Any] | None = None,
        vector_store_id: str | None = None,
    ) -> str:
        ...


class StreamJobAd(Protocol):
    """Callable signature for ``openai_utils.stream_job_ad``."""

    def __call__(
        self,
        session_data: Mapping[str, Any],
        selected_fields: Sequence[str],
        /,
        *,
        target_audience: str,
        manual_sections: Sequence[Mapping[str, str]] | None = None,
        style_reference: str | None = None,
        tone: str | None = None,
        lang: str | None = None,
        model: str | None = None,
        selected_values: Mapping[str, Any] | None = None,
        vector_store_id: str | None = None,
    ) -> Tuple[Any, str]:
        ...


class GenerateInterviewGuide(Protocol):
    """Callable signature for ``openai_utils.generate_interview_guide``."""

    def __call__(
        self,
        job_title: str,
        responsibilities: str = "",
        hard_skills: Sequence[str] | str = "",
        soft_skills: Sequence[str] | str = "",
        audience: str = "general",
        num_questions: int = 5,
        lang: str = "en",
        company_culture: str = "",
        tone: str | None = None,
        vector_store_id: str | None = None,
        model: str | None = None,
    ) -> Any:
        ...


@lru_cache(maxsize=1)
def _load_openai_utils() -> Any:
    """Return the ``openai_utils`` module lazily."""

    return import_module("openai_utils")


@lru_cache(maxsize=1)
def _load_openai_tools() -> Any:
    """Return the ``openai_utils.tools`` module lazily."""

    return import_module("openai_utils.tools")


def get_call_chat_api() -> CallChatApi:
    """Return the ``call_chat_api`` helper from ``openai_utils``."""

    module = _load_openai_utils()
    return cast(CallChatApi, getattr(module, "call_chat_api"))


def call_chat_api(*args: Any, **kwargs: Any) -> Any:
    """Proxy ``openai_utils.call_chat_api`` with lazy loading."""

    return get_call_chat_api()(*args, **kwargs)


def get_build_file_search_tool() -> BuildFileSearchTool:
    """Return the ``build_file_search_tool`` helper from ``openai_utils.tools``."""

    module = _load_openai_tools()
    return cast(BuildFileSearchTool, getattr(module, "build_file_search_tool"))


def build_file_search_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Proxy ``openai_utils.tools.build_file_search_tool`` with lazy loading."""

    return get_build_file_search_tool()(*args, **kwargs)


def get_generate_job_ad() -> GenerateJobAd:
    """Return the ``generate_job_ad`` helper from ``openai_utils``."""

    module = _load_openai_utils()
    return cast(GenerateJobAd, getattr(module, "generate_job_ad"))


def generate_job_ad(*args: Any, **kwargs: Any) -> str:
    """Proxy ``openai_utils.generate_job_ad`` with lazy loading."""

    return get_generate_job_ad()(*args, **kwargs)


def get_stream_job_ad() -> StreamJobAd:
    """Return the ``stream_job_ad`` helper from ``openai_utils``."""

    module = _load_openai_utils()
    return cast(StreamJobAd, getattr(module, "stream_job_ad"))


def stream_job_ad(*args: Any, **kwargs: Any) -> Tuple[Any, str]:
    """Proxy ``openai_utils.stream_job_ad`` with lazy loading."""

    return get_stream_job_ad()(*args, **kwargs)


def get_generate_interview_guide() -> GenerateInterviewGuide:
    """Return the ``generate_interview_guide`` helper from ``openai_utils``."""

    module = _load_openai_utils()
    return cast(GenerateInterviewGuide, getattr(module, "generate_interview_guide"))


def generate_interview_guide(*args: Any, **kwargs: Any) -> Any:
    """Proxy ``openai_utils.generate_interview_guide`` with lazy loading."""

    return get_generate_interview_guide()(*args, **kwargs)


__all__ = [
    "CallChatApi",
    "BuildFileSearchTool",
    "GenerateJobAd",
    "StreamJobAd",
    "GenerateInterviewGuide",
    "call_chat_api",
    "build_file_search_tool",
    "generate_job_ad",
    "stream_job_ad",
    "generate_interview_guide",
    "get_call_chat_api",
    "get_build_file_search_tool",
    "get_generate_interview_guide",
    "get_generate_job_ad",
    "get_stream_job_ad",
]
