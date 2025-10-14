"""Helper utilities for dual LLM evaluations."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from openai_utils import ChatCallResult, call_chat_api


def run_dual_prompt(
    primary_messages: Sequence[dict[str, Any]],
    secondary_messages: Sequence[dict[str, Any]],
    *,
    label: str | None = None,
    dispatch: str = "parallel",
    comparison_kwargs: Mapping[str, Any] | None = None,
    comparison_metadata_builder: Callable[[ChatCallResult, ChatCallResult], Mapping[str, Any]] | None = None,
    **base_kwargs: Any,
) -> ChatCallResult:
    """Evaluate two prompts and return the combined :class:`ChatCallResult`.

    Args:
        primary_messages: Prompt dispatched as the canonical request.
        secondary_messages: Alternate prompt evaluated for comparison.
        label: Optional label stored in the comparison metadata.
        dispatch: ``"parallel"`` (default) for concurrent execution or
            ``"sequential"`` to run one after another.
        comparison_kwargs: Additional overrides forwarded to
            :func:`openai_utils.api.call_chat_api` for the secondary request.
        comparison_metadata_builder: Optional callable result stored in the
            comparison metadata under the ``"custom"`` key.
        **base_kwargs: Keyword arguments forwarded to
            :func:`openai_utils.api.call_chat_api`.

    Returns:
        The combined :class:`ChatCallResult` containing both responses.
    """

    options = dict(comparison_kwargs or {})
    if comparison_metadata_builder is not None:
        options["metadata_builder"] = comparison_metadata_builder
    if label is not None:
        options["label"] = label
    if dispatch:
        options.setdefault("dispatch", dispatch)

    return call_chat_api(
        primary_messages,
        comparison_messages=secondary_messages,
        comparison_options=options,
        **base_kwargs,
    )


__all__ = ["run_dual_prompt"]
