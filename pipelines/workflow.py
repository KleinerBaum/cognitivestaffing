"""Lightweight workflow engine for orchestrating LLM task sequences."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    wait,
)
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from typing import Any, Callable, Iterable, Mapping

try:
    from streamlit.runtime.scriptruncontext import add_script_run_ctx, get_script_run_ctx
except (ModuleNotFoundError, RuntimeError):
    add_script_run_ctx = None
    get_script_run_ctx = None

from utils.logging_context import (
    configure_logging,
    log_context,
    set_pipeline_task,
    wrap_with_current_context,
)

configure_logging()

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - thin wrapper
        super().__init__(*args, **kwargs)
        self._lock = Lock()

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            super().__setitem__(key, value)

    def update(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401 - thin wrapper
        with self._lock:
            super().update(*args, **kwargs)


@dataclass(frozen=True)
class Task:
    """Executable unit within a workflow graph."""

    name: str
    func: WorkflowCallable
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    retries: int = 0
    timeout: float | None = None
    parallelizable: bool = True

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

    def __init__(
        self,
        tasks: Iterable[Task],
        *,
        logger_: logging.Logger | None = None,
        max_workers: int | None = None,
    ):
        tasks_list = list(tasks)
        self._logger = logger_ or logger
        self._tasks: dict[str, Task] = {task.name: task for task in tasks_list}
        if len(self._tasks) != len(tasks_list):
            raise ValueError("Task names must be unique within a workflow")
        self._order = self._resolve_order()
        self._max_workers = max_workers

    def run(self, context: Mapping[str, Any] | None = None) -> WorkflowRunResult:
        ctx = WorkflowContext(context or {})
        results: dict[str, TaskResult] = {name: TaskResult() for name in self._tasks}
        script_run_ctx = get_script_run_ctx() if get_script_run_ctx else None

        dependants: dict[str, list[str]] = defaultdict(list)
        pending_dependencies: dict[str, int] = {}
        for task in self._tasks.values():
            pending_dependencies[task.name] = len(task.dependencies)
            for dependency in task.dependencies:
                dependants[dependency].append(task.name)

        ready: deque[str] = deque([name for name, count in pending_dependencies.items() if count == 0])
        in_flight: dict[Future[tuple[Any, int]], Task] = {}

        with ThreadPoolExecutor(max_workers=self._max_workers or len(self._tasks)) as executor:
            while ready or in_flight:
                while ready:
                    candidate_name = ready.popleft()
                    candidate_task = self._tasks[candidate_name]
                    outcome = results[candidate_name]

                    with log_context(pipeline_task=candidate_task.name):
                        if self._should_skip(candidate_task, results):
                            outcome.status = TaskStatus.SKIPPED
                            self._logger.info("Skipping task %s due to failed dependencies", candidate_task.name)
                            for child in dependants[candidate_name]:
                                pending_dependencies[child] -= 1
                                if pending_dependencies[child] == 0:
                                    ready.append(child)
                            continue

                    if not candidate_task.parallelizable and in_flight:
                        done, _ = wait(in_flight.keys())
                        self._collect_finished(done, in_flight, results, ctx, dependants, pending_dependencies, ready)
                        ready.appendleft(candidate_name)
                        continue

                    with log_context(pipeline_task=candidate_task.name):
                        self._logger.info("Starting task %s", candidate_task.name)
                    outcome.status = TaskStatus.RUNNING
                    future = executor.submit(
                        wrap_with_current_context(self._execute, candidate_task, ctx, script_run_ctx)
                    )
                    if add_script_run_ctx and script_run_ctx:
                        add_script_run_ctx(future, script_run_ctx)
                    in_flight[future] = candidate_task

                    if not candidate_task.parallelizable:
                        break

                if not in_flight:
                    continue

                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                self._collect_finished(done, in_flight, results, ctx, dependants, pending_dependencies, ready)

        return WorkflowRunResult(results=results, context=ctx)

    def _collect_finished(
        self,
        finished: set[Future[tuple[Any, int]]],
        in_flight: dict[Future[tuple[Any, int]], Task],
        results: dict[str, TaskResult],
        ctx: WorkflowContext,
        dependants: Mapping[str, list[str]],
        pending_dependencies: dict[str, int],
        ready: deque[str],
    ) -> None:
        for future in finished:
            task = in_flight.pop(future)
            outcome = results[task.name]
            try:
                result, attempts_used = future.result()
            except SkipTask as skip_exc:
                outcome.status = TaskStatus.SKIPPED
                outcome.error = skip_exc
                outcome.attempts = getattr(skip_exc, "attempts", 1)
                with log_context(pipeline_task=task.name):
                    self._logger.info("Task %s marked as skipped: %s", task.name, skip_exc)
            except Exception as exc:  # noqa: BLE001 - capture for status tracking
                outcome.status = TaskStatus.FAILED
                outcome.error = exc
                outcome.attempts = getattr(exc, "attempts", 1)
                with log_context(pipeline_task=task.name):
                    self._logger.exception("Task %s failed", task.name)
            else:
                outcome.status = TaskStatus.SUCCESS
                outcome.result = result
                outcome.attempts = attempts_used
                ctx[task.name] = result
                with log_context(pipeline_task=task.name):
                    self._logger.info("Completed task %s", task.name)

            for child in dependants.get(task.name, []):
                pending_dependencies[child] -= 1
                if pending_dependencies[child] == 0:
                    ready.append(child)

    def _execute(self, task: Task, context: WorkflowContext, script_run_ctx: Any | None = None) -> tuple[Any, int]:
        attempts = 0
        last_error: Exception | None = None
        with log_context(pipeline_task=task.name):
            set_pipeline_task(task.name)
            for attempt in range(task.retries + 1):
                attempts = attempt + 1
                try:
                    if task.timeout is not None:
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(wrap_with_current_context(task.func, context))
                            if add_script_run_ctx and script_run_ctx:
                                add_script_run_ctx(future, script_run_ctx)
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
