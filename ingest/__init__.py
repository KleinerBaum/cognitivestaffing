"""Utilities for ingesting job description text."""

from .reader import read_job_text
from .ocr import ocr_pdf, select_ocr_backend

__all__ = ["read_job_text", "ocr_pdf", "select_ocr_backend"]
