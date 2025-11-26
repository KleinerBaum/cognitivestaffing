from __future__ import annotations

import pytest

from pipelines.workflow import SkipTask, Task, TaskStatus, WorkflowContext, WorkflowRunner


def test_workflow_executes_in_dependency_order() -> None:
    order: list[str] = []

    def first(context: WorkflowContext) -> str:
        order.append("first")
        context["seed"] = "value"
        return "value"

    def second(context: WorkflowContext) -> str:
        order.append("second")
        return f"{context['seed']}-child"

    runner = WorkflowRunner(
        [
            Task(name="first", func=first),
            Task(name="second", func=second, dependencies=("first",)),
        ]
    )

    result = runner.run()

    assert order == ["first", "second"]
    assert result.get("first").status is TaskStatus.SUCCESS
    assert result.get("second").status is TaskStatus.SUCCESS
    assert result.context["first"] == "value"
    assert result.context["second"] == "value-child"


def test_workflow_retries_and_skips_dependants() -> None:
    attempts: dict[str, int] = {"flaky": 0}

    def flaky(_: WorkflowContext) -> str:
        attempts["flaky"] += 1
        if attempts["flaky"] < 2:
            raise RuntimeError("boom")
        return "ok"

    def downstream(_: WorkflowContext) -> str:
        return "downstream"

    runner = WorkflowRunner(
        [
            Task(name="flaky", func=flaky, retries=1),
            Task(name="dependent", func=downstream, dependencies=("flaky",)),
        ]
    )

    result = runner.run()

    assert attempts["flaky"] == 2
    assert result.get("flaky").status is TaskStatus.SUCCESS
    assert result.get("dependent").status is TaskStatus.SUCCESS
    assert result.context["dependent"] == "downstream"


@pytest.mark.parametrize("retries", [0, 1])
def test_failed_task_marks_dependants_skipped(retries: int) -> None:
    def failing(_: WorkflowContext) -> str:
        raise ValueError("nope")

    def needs_parent(_: WorkflowContext) -> str:
        return "unreachable"

    runner = WorkflowRunner(
        [
            Task(name="parent", func=failing, retries=retries),
            Task(name="child", func=needs_parent, dependencies=("parent",)),
        ]
    )

    result = runner.run()

    assert result.get("parent").status is TaskStatus.FAILED
    assert isinstance(result.get("parent").error, ValueError)
    assert result.get("child").status is TaskStatus.SKIPPED


def test_tasks_can_signal_skip_without_error() -> None:
    def skip_me(_: WorkflowContext) -> str:
        raise SkipTask("disabled")

    runner = WorkflowRunner([Task(name="skip", func=skip_me)])

    result = runner.run()

    assert result.get("skip").status is TaskStatus.SKIPPED
    assert str(result.get("skip").error) == "disabled"
