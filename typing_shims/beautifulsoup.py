"""Typed shim for BeautifulSoup usage."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["BeautifulSoup", "Tag"]

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Any, Mapping, Protocol, runtime_checkable

    @runtime_checkable
    class Tag(Protocol):
        """Subset of the ``bs4.element.Tag`` API relied upon by the parsers."""

        name: str | None
        attrs: Mapping[str, Any]

        def get(self, key: str, default: Any | None = None) -> Any: ...

        def get_text(self, separator: str = " ", strip: bool = False) -> str: ...

        def find(
            self,
            name: str | Sequence[str] | None = None,
            attrs: Mapping[str, Any] | None = None,
            recursive: bool = True,
            text: Any | None = None,
            limit: int | None = None,
        ) -> "Tag" | None: ...

        def find_all(
            self,
            name: str | Sequence[str] | None = None,
            attrs: Mapping[str, Any] | None = None,
            recursive: bool = True,
            text: Any | None = None,
            limit: int | None = None,
        ) -> list["Tag"]: ...

        def select_one(self, selector: str) -> "Tag" | None: ...

        @property
        def parents(self) -> Iterable["Tag"]: ...

    class BeautifulSoup(Protocol):
        """Typed representation of ``bs4.BeautifulSoup`` objects."""

        def __init__(self, markup: str | bytes, features: str | None = None, **kwargs: Any) -> None: ...

        def select_one(self, selector: str) -> Tag | None: ...

        def find(
            self,
            name: str | Sequence[str] | None = None,
            attrs: Mapping[str, Any] | None = None,
            recursive: bool = True,
            text: Any | None = None,
            limit: int | None = None,
        ) -> Tag | None: ...

        def find_all(
            self,
            name: str | Sequence[str] | None = None,
            attrs: Mapping[str, Any] | None = None,
            recursive: bool = True,
            text: Any | None = None,
            limit: int | None = None,
        ) -> list[Tag]: ...
else:  # pragma: no cover - passthrough import
    from bs4 import BeautifulSoup
    from bs4.element import Tag
