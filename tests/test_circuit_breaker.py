from __future__ import annotations

from typing import Any

from utils.circuit_breaker import CircuitBreaker, CircuitState


def _clock_generator(start: float = 0.0):
    current = {"value": start}

    def _tick() -> float:
        return current["value"]

    def _advance(delta: float) -> float:
        current["value"] += delta
        return current["value"]

    return _tick, _advance


def test_breaker_opens_after_consecutive_failures() -> None:
    clock, advance = _clock_generator()
    store: dict[str, Any] = {}
    breaker = CircuitBreaker(
        "clearbit",
        store=store,
        failure_threshold=3,
        recovery_timeout=10,
        clock=clock,
    )

    assert breaker.allow_request()
    for _ in range(3):
        breaker.record_failure()
    state = breaker.current_state()
    assert state.state is CircuitState.OPEN
    assert state.failure_count == 3
    assert not breaker.allow_request()

    advance(11)
    assert breaker.allow_request()
    breaker.record_failure()
    assert breaker.current_state().state is CircuitState.OPEN
    assert not breaker.allow_request()


def test_breaker_closes_after_half_open_success() -> None:
    clock, advance = _clock_generator()
    store: dict[str, Any] = {}
    breaker = CircuitBreaker(
        "clearbit",
        store=store,
        failure_threshold=2,
        recovery_timeout=5,
        clock=clock,
    )

    breaker.record_failure()
    breaker.record_failure()
    assert breaker.current_state().state is CircuitState.OPEN
    assert not breaker.allow_request()

    advance(6)
    assert breaker.allow_request()
    breaker.record_success()
    state = breaker.current_state()
    assert state.state is CircuitState.CLOSED
    assert state.failure_count == 0
    assert breaker.allow_request()
