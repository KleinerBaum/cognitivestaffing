"""Typed shim for ``streamlit.components.v1``."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["html"]

if TYPE_CHECKING:
    from typing import Any

    def html(
        body: str,
        *,
        height: int | None = None,
        width: int | None = None,
        scrolling: bool = False,
        **kwargs: Any,
    ) -> None: ...
else:  # pragma: no cover - passthrough import only
    from streamlit.components.v1 import html
