"""Utilities for ingesting job posting text."""

from .extractors import extract_text_from_file, extract_text_from_url
from .reader import clean_job_text, clean_structured_document, read_job_text
from .types import ContentBlock, StructuredDocument, build_plain_text_document

__all__ = [
    "read_job_text",
    "extract_text_from_file",
    "extract_text_from_url",
    "clean_job_text",
    "clean_structured_document",
    "ContentBlock",
    "StructuredDocument",
    "build_plain_text_document",
]
