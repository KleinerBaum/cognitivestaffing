"""Domain-specific exception hierarchy for OpenAI integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class NeedAnalysisPipelineError(Exception):
    """Base exception for orchestrating need analysis pipelines."""

    message: str
    step: str | None = None
    model: str | None = None
    schema: str | None = None
    details: Mapping[str, Any] | None = None
    original: Exception | None = None

    def __str__(self) -> str:
        return self.message


@dataclass
class SchemaValidationError(NeedAnalysisPipelineError):
    """Raised when the model rejects or cannot honour the provided schema."""


@dataclass
class LLMResponseFormatError(NeedAnalysisPipelineError):
    """Raised when the LLM returns malformed or unparsable output."""

    raw_content: str | None = None


@dataclass
class ExternalServiceError(NeedAnalysisPipelineError):
    """Raised when an upstream dependency returns an error."""

    service: str | None = None
