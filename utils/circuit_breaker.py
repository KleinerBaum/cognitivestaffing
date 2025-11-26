from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any, MutableMapping, Callable
import time


logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Possible circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerState:
    """In-memory representation of a circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_ts: float | None = None


class CircuitBreaker:
    """Minimal circuit breaker for per-session external service calls."""

    def __init__(
        self,
        service_name: str,
        *,
        store: MutableMapping[str, Any] | None = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold < 1:
            msg = "failure_threshold must be >= 1"
            raise ValueError(msg)
        self.service_name = service_name
        self._store = store
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock or time.monotonic
        self._state_key = f"circuit_breaker.{service_name}"

    def allow_request(self) -> bool:
        """Return ``True`` when the circuit permits another call."""

        state = self._load_state()
        now = self._clock()
        if state.state == CircuitState.OPEN:
            if state.last_failure_ts is not None and now - state.last_failure_ts >= self.recovery_timeout:
                state.state = CircuitState.HALF_OPEN
                self._persist_state(state)
                return True
            return False
        return True

    def record_failure(self) -> None:
        """Record a failed attempt and open the circuit when needed."""

        state = self._load_state()
        state.failure_count += 1
        state.last_failure_ts = self._clock()
        if state.state == CircuitState.HALF_OPEN or state.failure_count >= self.failure_threshold:
            state.state = CircuitState.OPEN
        self._persist_state(state)

    def record_success(self) -> None:
        """Reset the circuit breaker after a successful call."""

        state = CircuitBreakerState()
        self._persist_state(state)

    def current_state(self) -> CircuitBreakerState:
        """Return a copy of the current breaker state."""

        state = self._load_state()
        return CircuitBreakerState(
            state=state.state,
            failure_count=state.failure_count,
            last_failure_ts=state.last_failure_ts,
        )

    def _load_state(self) -> CircuitBreakerState:
        if self._store is None:
            return CircuitBreakerState()
        raw = self._store.get(self._state_key)
        if not isinstance(raw, dict):
            return CircuitBreakerState()
        state_raw = raw.get("state")
        failure_count = raw.get("failure_count")
        last_failure_ts = raw.get("last_failure_ts")
        if isinstance(state_raw, str):
            try:
                circuit_state = CircuitState(state_raw)
            except ValueError:
                circuit_state = CircuitState.CLOSED
        else:
            circuit_state = CircuitState.CLOSED
        if not isinstance(failure_count, int):
            failure_count = 0
        if not isinstance(last_failure_ts, (int, float)):
            last_failure_ts = None
        return CircuitBreakerState(
            state=circuit_state,
            failure_count=failure_count,
            last_failure_ts=last_failure_ts,
        )

    def _persist_state(self, state: CircuitBreakerState) -> None:
        if self._store is None:
            return
        self._store[self._state_key] = {
            "state": state.state.value,
            "failure_count": state.failure_count,
            "last_failure_ts": state.last_failure_ts,
        }
