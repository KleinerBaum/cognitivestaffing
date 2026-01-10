from __future__ import annotations

"""Compatibility shim for wizard navigation controller."""

from wizard.navigation.router import BadRequestError, NavigationController, PageProgressSnapshot

__all__ = [
    "BadRequestError",
    "NavigationController",
    "PageProgressSnapshot",
]
