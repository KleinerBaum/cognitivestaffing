from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from typing import Iterator

_DEFAULT_LOG_FORMAT = (
    "%(asctime)s %(levelname)s [session=%(session_id)s step=%(wizard_step)s "
    "pipeline=%(pipeline_task)s model=%(model)s] %(name)s: %(message)s"
)

_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="-")
_wizard_step_var: contextvars.ContextVar[str] = contextvars.ContextVar("wizard_step", default="-")
_pipeline_task_var: contextvars.ContextVar[str] = contextvars.ContextVar("pipeline_task", default="-")
_model_var: contextvars.ContextVar[str] = contextvars.ContextVar("model", default="-")
_DEFAULT_RECORD_FACTORY = logging.getLogRecordFactory()
_RECORD_FACTORY_INSTALLED = False


def _apply_context(record: logging.LogRecord) -> None:
    record.session_id = _session_id_var.get("-")
    record.wizard_step = _wizard_step_var.get("-")
    record.pipeline_task = _pipeline_task_var.get("-")
    record.model = _model_var.get("-")


class _ContextFilter(logging.Filter):
    """Inject contextual fields into log records for consistent formatting."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - logging protocol
        _apply_context(record)
        return True


def _coerce(value: str | None) -> str:
    if value is None:
        return "-"
    stripped = value.strip()
    return stripped or "-"


def configure_logging(*, level: int = logging.INFO) -> None:
    """Ensure the root logger formats records with contextual metadata."""

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_DEFAULT_LOG_FORMAT)
        root = logging.getLogger()
    for handler in root.handlers:
        formatter = handler.formatter or logging.Formatter(_DEFAULT_LOG_FORMAT)
        handler.setFormatter(formatter)
    has_filter = any(isinstance(flt, _ContextFilter) for flt in root.filters)
    if not has_filter:
        root.addFilter(_ContextFilter())
    global _RECORD_FACTORY_INSTALLED
    if not _RECORD_FACTORY_INSTALLED:
        default_factory = _DEFAULT_RECORD_FACTORY

        def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
            record = default_factory(*args, **kwargs)
            _apply_context(record)
            return record

        logging.setLogRecordFactory(_record_factory)
        _RECORD_FACTORY_INSTALLED = True


def set_session_id(session_id: str | None) -> None:
    """Bind a session identifier for subsequent log records."""

    configure_logging()
    _session_id_var.set(_coerce(session_id))


def set_wizard_step(step: str | None) -> None:
    """Bind the current wizard step to the logging context."""

    _wizard_step_var.set(_coerce(step))


def set_pipeline_task(task: str | None) -> None:
    """Bind the active pipeline or workflow task to the logging context."""

    _pipeline_task_var.set(_coerce(task))


def set_model(model: str | None) -> None:
    """Bind the active model identifier to the logging context."""

    _model_var.set(_coerce(model))


@contextmanager
def log_context(
    *,
    session_id: str | None = None,
    wizard_step: str | None = None,
    pipeline_task: str | None = None,
    model: str | None = None,
) -> Iterator[None]:
    """Temporarily override logging context variables."""

    tokens: list[tuple[contextvars.ContextVar[str], contextvars.Token[str]]] = []
    if session_id is not None:
        tokens.append((_session_id_var, _session_id_var.set(_coerce(session_id))))
    if wizard_step is not None:
        tokens.append((_wizard_step_var, _wizard_step_var.set(_coerce(wizard_step))))
    if pipeline_task is not None:
        tokens.append((_pipeline_task_var, _pipeline_task_var.set(_coerce(pipeline_task))))
    if model is not None:
        tokens.append((_model_var, _model_var.set(_coerce(model))))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
