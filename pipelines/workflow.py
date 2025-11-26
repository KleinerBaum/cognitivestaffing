"""Lightweight workflow engine for orchestrating LLM task sequences."""

from __future__ import annotations

import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping

logger = logging.getLogger(__name__)

WorkflowCallable = Callable[["WorkflowContext"], Any]


class TaskStatus(StrEnum):
    """Life-cycle status for workflow tasks."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class SkipTask(RuntimeError):
    """Signal that a task was intentionally skipped."""


class WorkflowContext(dict[str, Any]):
    """Mutable context shared between workflow tasks."""


@dataclass(frozen=True)
class Task:
    """Executable unit within a workflow graph."""

    name: str
    func: WorkflowCallable
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    retries: int = 0
    timeout: float | None = None

    def __post_init__(self) -> None:
        if self.retries < 0:
            raise ValueError("retries must be >= 0")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive when provided")


@dataclass
class TaskResult:
    """Outcome of an executed task."""

    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: Exception | None = None
    attempts: int = 0


@dataclass
class WorkflowRunResult:
    """Container for workflow execution results."""

    results: Mapping[str, TaskResult]
    context: WorkflowContext

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return a serialisable representation of task outcomes."""

        serialised: dict[str, dict[str, Any]] = {}
        for name, outcome in self.results.items():
            serialised[name] = {
                "status": outcome.status.value,
                "attempts": outcome.attempts,
                "error": str(outcome.error) if outcome.error else None,
            }
        return serialised

    def get(self, name: str) -> TaskResult | None:
        return self.results.get(name)


class WorkflowRunner:
    """Execute tasks in dependency order with retry/timeout handling."""

    def __init__(self, tasks: Iterable[Task], *, logger_: logging.Logger | None = None):
        tasks_list = list(tasks)
        self._logger = logger_ or logger
        self._tasks: dict[str, Task] = {task.name: task for task in tasks_list}
        if len(self._tasks) != len(tasks_list):
            raise ValueError("Task names must be unique within a workflow")
        self._order = self._resolve_order()

    def run(self, context: Mapping[str, Any] | None = None) -> WorkflowRunResult:
        ctx = WorkflowContext(context or {})
        results: dict[str, TaskResult] = {name: TaskResult() for name in self._tasks}

        for task_name in self._order:
            task = self._tasks[task_name]
            outcome = results[task_name]
            if self._should_skip(task, results):
                outcome.status = TaskStatus.SKIPPED
                self._logger.info("Skipping task %s due to failed dependencies", task.name)
                continue

            self._logger.info("Starting task %s", task.name)
            outcome.status = TaskStatus.RUNNING
            try:
                result, attempts_used = self._execute(task, ctx)
            except SkipTask as skip_exc:
                outcome.status = TaskStatus.SKIPPED
                outcome.error = skip_exc
                outcome.attempts = getattr(skip_exc, "attempts", 1)
                self._logger.info("Task %s marked as skipped: %s", task.name, skip_exc)
            except Exception as exc:  # noqa: BLE001 - capture for status tracking
                outcome.status = TaskStatus.FAILED
                outcome.error = exc
                outcome.attempts = getattr(exc, "attempts", 1)
                self._logger.exception("Task %s failed", task.name)
            else:
                outcome.status = TaskStatus.SUCCESS
                outcome.result = result
                outcome.attempts = attempts_used
                ctx[task.name] = result
                self._logger.info("Completed task %s", task.name)

        return WorkflowRunResult(results=results, context=ctx)

    def _execute(self, task: Task, context: WorkflowContext) -> tuple[Any, int]:
        attempts = 0
        last_error: Exception | None = None
        for attempt in range(task.retries + 1):
            attempts = attempt + 1
            try:
                if task.timeout is not None:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(task.func, context)
                        return future.result(timeout=task.timeout), attempts
                return task.func(context), attempts
            except SkipTask as exc:
                setattr(exc, "attempts", attempts)
                raise
            except FuturesTimeoutError as exc:
                last_error = exc
                self._logger.warning(
                    "Task %s exceeded timeout after %.2fs (attempt %s/%s)",
                    task.name,
                    task.timeout,
                    attempts,
                    task.retries + 1,
                )
            except Exception as exc:  # noqa: BLE001 - propagate to retry handler
                last_error = exc
                if attempt < task.retries:
                    self._logger.warning(
                        "Task %s failed (attempt %s/%s); retrying",
                        task.name,
                        attempts,
                        task.retries + 1,
                        exc_info=exc,
                    )
                else:
                    self._logger.debug("Task %s failed on final attempt", task.name)
            if last_error and attempt < task.retries:
                continue
        if last_error:
            if hasattr(last_error, "args"):
                setattr(last_error, "attempts", attempts)
            raise last_error
        fallback_error = RuntimeError(f"Task {task.name} failed without raising an exception")
        setattr(fallback_error, "attempts", attempts)
        raise fallback_error

    def _resolve_order(self) -> list[str]:
        indegree: dict[str, int] = {name: 0 for name in self._tasks}
        for task in self._tasks.values():
            for dep in task.dependencies:
                if dep not in self._tasks:
                    raise ValueError(f"Unknown dependency '{dep}' for task '{task.name}'")
                indegree[task.name] += 1

        queue: deque[str] = deque([name for name, degree in indegree.items() if degree == 0])
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for candidate in self._tasks.values():
                if current in candidate.dependencies:
                    indegree[candidate.name] -= 1
                    if indegree[candidate.name] == 0:
                        queue.append(candidate.name)

        if len(order) != len(self._tasks):
            raise ValueError("Workflow graph contains a cycle; cannot resolve execution order")
        return order

    @staticmethod
    def _should_skip(task: Task, results: Mapping[str, TaskResult]) -> bool:
        if not task.dependencies:
            return False
        return any(results[dep].status is not TaskStatus.SUCCESS for dep in task.dependencies)
