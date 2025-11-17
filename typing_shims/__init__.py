"""Runtime-friendly typing helpers for third-party libraries.

This package exposes small shims for libraries that lack precise type
information. Each shim re-exports the real implementation at runtime so the
application behaves exactly as before while offering tight type hints to mypy.
"""

__all__ = [
    "streamlit",
    "requests",
    "beautifulsoup",
    "streamlit_components",
]
