"""Custom exception types for extraction and parsing."""

from __future__ import annotations


class ExtractionError(Exception):
    """Base exception for extraction related issues."""


class ModelResponseEmpty(ExtractionError):
    """Raised when the model produced an empty response."""


class JsonInvalid(ExtractionError):
    """Raised when a response could not be parsed as valid JSON."""
