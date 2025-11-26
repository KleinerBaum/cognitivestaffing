from __future__ import annotations

import logging
from typing import Any

from pipelines.workflow import Task, WorkflowRunner
from utils.logging_context import configure_logging, log_context, set_session_id


def _noop_task(context: dict[str, Any]) -> str:
    return "ok"


def test_workflow_logging_includes_context(caplog: Any) -> None:
    configure_logging()
    set_session_id("session-123")
    logger = logging.getLogger("test.logging.workflow")
    caplog.set_level(logging.INFO, logger=logger.name)
    runner = WorkflowRunner([Task(name="mock-task", func=_noop_task)], logger_=logger, max_workers=1)

    with log_context(wizard_step="step_company"):
        runner.run({})

    records = [record for record in caplog.records if "Starting task" in record.message]
    assert records, "Expected at least one task start log entry"
    record = records[0]
    assert record.session_id == "session-123"
    assert record.wizard_step == "step_company"
    assert record.pipeline_task == "mock-task"
