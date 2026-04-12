from __future__ import annotations

"""
Small shared utilities for the backend.

At the moment this module centralizes environment-variable handling so different parts
of the application (poller, globe integration, etc.) behave consistently.
"""

import os


def get_env(name: str, default: str) -> str:
    """
    Return an environment variable value, falling back to default if unset/blank.

    The returned value is stripped to avoid subtle configuration issues caused by
    leading/trailing whitespace in shell exports.
    """
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped != "" else default


def get_env_float(name: str, default: float) -> float:
    """Parse an environment variable as float, returning default when invalid/unset."""
    raw = get_env(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def get_env_int(name: str, default: int) -> int:
    """Parse an environment variable as int, returning default when invalid/unset."""
    raw = get_env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default
