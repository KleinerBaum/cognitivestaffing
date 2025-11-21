"""Generic retry utilities with exponential backoff."""

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, ParamSpec, TypeVar

import backoff
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

T = TypeVar("T")
P = ParamSpec("P")

# Retryable OpenAI exceptions shared across chat/responses calls.
OPENAI_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    APIError,
)


def retry(call: Callable[[], T], *, attempts: int = 2, base_delay: float = 0.5) -> T:
    """Execute ``call`` retrying with exponential backoff.

    Args:
        call: Zero-argument callable to execute.
        attempts: Maximum number of attempts.
        base_delay: Initial delay in seconds. Subsequent retries double this
            delay (0.5s, 1s, ...).

    Returns:
        The value returned by ``call``.

    Raises:
        The last exception raised by ``call`` if all attempts fail.
    """

    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return call()
        except Exception as exc:  # pragma: no cover - depends on caller
            last_exc = exc
            if i >= attempts - 1:
                break
            time.sleep(base_delay * (2**i))
    assert last_exc is not None
    raise last_exc


def retry_with_backoff(
    *,
    exceptions: Iterable[type[Exception]] = OPENAI_RETRY_EXCEPTIONS,
    max_tries: int = 3,
    giveup: Callable[[Exception], bool] | None = None,
    on_giveup: Callable[[Any], None] | Iterable[Callable[[Any], None]] | None = None,
    jitter: Any = backoff.full_jitter,
    logger: Any = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Return a decorator applying exponential backoff for ``exceptions``.

    This helper centralises the retry configuration so OpenAI chat and
    Responses calls can share the same guard rails while remaining testable.
    """

    exception_tuple: tuple[type[Exception], ...] = tuple(exceptions)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def default_giveup(_: Exception) -> bool:
            return False

        resolved_giveup: Callable[[Exception], bool]
        if giveup is None:
            resolved_giveup = default_giveup
        else:
            resolved_giveup = giveup

        return backoff.on_exception(
            backoff.expo,
            exception_tuple,
            max_tries=max_tries,
            jitter=jitter,
            giveup=resolved_giveup,
            on_giveup=on_giveup,
            logger=logger,
        )(func)

    return decorator
