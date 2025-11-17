"""Custom exception types for extraction and parsing."""

from __future__ import annotations


class ExtractionError(Exception):
    """Base exception for extraction related issues."""


AI_UNAVAILABLE_MESSAGE = (
    "The AI is currently unavailable, please try again later. / Die KI ist derzeit nicht"
    " erreichbar, bitte später erneut versuchen."
)


class ExtractionUnavailableError(ExtractionError):
    """Raised when the AI backend cannot be reached after retries."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or AI_UNAVAILABLE_MESSAGE)


class ModelResponseEmpty(ExtractionError):
    """Raised when the model produced an empty response."""


class JsonInvalid(ExtractionError):
    """Raised when a response could not be parsed as valid JSON."""
