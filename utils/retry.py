"""Generic retry utilities with exponential backoff."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


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
