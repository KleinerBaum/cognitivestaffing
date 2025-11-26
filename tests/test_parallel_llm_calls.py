from __future__ import annotations

import time

from pipelines.workflow import Task, TaskStatus, WorkflowContext, WorkflowRunner


def test_parallel_tasks_reduce_total_runtime() -> None:
    """Independent tasks without dependencies should run concurrently."""

    def skill_enrichment(_: WorkflowContext) -> str:
        time.sleep(0.4)
        return "skills"

    def compensation_range(_: WorkflowContext) -> str:
        time.sleep(0.6)
        return "compensation"

    def aggregate(context: WorkflowContext) -> tuple[str, str]:
        return context.get("skill_enrichment", ""), context.get("compensation_range", "")

    runner = WorkflowRunner(
        [
            Task(name="skill_enrichment", func=skill_enrichment, parallelizable=True),
            Task(name="compensation_range", func=compensation_range, parallelizable=True),
            Task(name="aggregate", func=aggregate, dependencies=("skill_enrichment", "compensation_range")),
        ],
        max_workers=3,
    )

    started = time.perf_counter()
    result = runner.run()
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, "parallel tasks should complete near the longest individual duration"
    assert result.get("skill_enrichment").status is TaskStatus.SUCCESS
    assert result.get("compensation_range").status is TaskStatus.SUCCESS
    assert result.get("aggregate").result == ("skills", "compensation")
