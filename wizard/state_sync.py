"""Compatibility shim for widget/profile state sync helpers."""

from __future__ import annotations

from wizard.navigation.state import iter_profile_scalars, prime_widget_state_from_profile

__all__ = [
    "iter_profile_scalars",
    "prime_widget_state_from_profile",
]
