from __future__ import annotations

"""utils.py - Hilfsfunktionen.

Allgemeine Helfer, z.B. für das Auslesen von Umgebungsvariablen.
"""

import os


def get_env(name: str, default: str) -> str:
    """Gibt den Wert einer Umgebungsvariablen zurück oder den Standardwert, falls leer/nicht gesetzt.

    Der zurückgegebene Wert wird bereinigt (stripped), um subtile Konfigurationsfehler
    durch führende oder nachfolgende Leerzeichen in Shell-Exports zu vermeiden.
    """
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped != "" else default


def get_env_float(name: str, default: float) -> float:
    """Liest eine Float-Umgebungsvariable aus.

    Gibt `default` zurück, wenn die Variable nicht existiert, leer ist
    oder nicht in einen Float umgewandelt werden kann.
    """
    raw = get_env(name, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def get_env_int(name: str, default: int) -> int:
    """Liest eine Integer-Umgebungsvariable aus, gibt bei Fehler/Fehlen den Standardwert zurück."""
    raw = get_env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default
