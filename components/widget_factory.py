"""Factories for profile-bound wizard widgets (Widget Factory Pattern)."""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

from wizard._layout import (
    profile_multiselect as _profile_multiselect,
    profile_selectbox as _profile_selectbox,
    profile_text_input as _profile_text_input,
)

T = TypeVar("T")


def text_input(
    path: str,
    label: str,
    *,
    placeholder: str | None = None,
    key: str | None = None,
    default: Any | None = None,
    value_formatter: Callable[[Any | None], str] | None = None,
    widget_factory: Callable[..., str] | None = None,
    **kwargs: Any,
) -> str:
    """Render a profile-bound text input using the shared widget factory."""

    return _profile_text_input(
        path,
        label,
        placeholder=placeholder,
        key=key,
        default=default,
        value_formatter=value_formatter,
        widget_factory=widget_factory,
        **kwargs,
    )


def select(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: T | None = None,
    widget_factory: Callable[..., T] | None = None,
    **kwargs: Any,
) -> T:
    """Render a profile-bound select widget using the shared factory."""

    return _profile_selectbox(
        path,
        label,
        options,
        key=key,
        default=default,
        widget_factory=widget_factory,
        **kwargs,
    )


def multiselect(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: Sequence[T] | None = None,
    widget_factory: Callable[..., Sequence[T]] | None = None,
    **kwargs: Any,
) -> list[T]:
    """Render a profile-bound multiselect widget using the shared factory."""

    return list(
        _profile_multiselect(
            path,
            label,
            options,
            key=key,
            default=default,
            widget_factory=widget_factory,
            **kwargs,
        )
    )


__all__ = ["text_input", "select", "multiselect"]
