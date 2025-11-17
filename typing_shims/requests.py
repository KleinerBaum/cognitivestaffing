"""Typed shim for the subset of the ``requests`` API that we exercise."""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "get",
    "post",
    "Session",
    "Response",
    "RequestException",
    "HTTPError",
    "Timeout",
]

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping
    from types import TracebackType
    from typing import Any, Protocol

    class Response(Protocol):
        """Requests response object used across the ingestion utilities."""

        status_code: int
        headers: Mapping[str, str]
        text: str
        content: bytes

        def raise_for_status(self) -> None: ...

        def json(self, **kwargs: Any) -> Any: ...

    class Session(Protocol):
        """Subset of the ``requests.Session`` API we rely on."""

        headers: MutableMapping[str, str]

        def __enter__(self) -> "Session": ...

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool | None: ...

        def get(
            self,
            url: str,
            *,
            params: Mapping[str, Any] | None = None,
            data: Any | None = None,
            headers: Mapping[str, str] | None = None,
            timeout: float | tuple[float, float] | None = None,
            allow_redirects: bool = True,
        ) -> Response: ...

        def post(
            self,
            url: str,
            *,
            data: Any | None = None,
            json: Any | None = None,
            headers: Mapping[str, str] | None = None,
            timeout: float | tuple[float, float] | None = None,
        ) -> Response: ...

        def close(self) -> None: ...

    class RequestException(Exception): ...

    class HTTPError(RequestException): ...

    class Timeout(RequestException): ...

    def get(
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | tuple[float, float] | None = None,
        allow_redirects: bool = True,
    ) -> Response: ...

    def post(
        url: str,
        *,
        data: Any | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | tuple[float, float] | None = None,
    ) -> Response: ...
else:  # pragma: no cover - import side effect only
    from requests import HTTPError, RequestException, Response, Session, Timeout, get, post
