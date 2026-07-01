from __future__ import annotations

"""system_position.py - Liest die Systemkoordinaten aus.

Verwendet SYSTEM_LAT und SYSTEM_LON Umgebungsvariablen.
"""

from typing import Any

from ..utils import get_env

def _read_env_position() -> dict[str, Any] | None:
    lat_raw = get_env("SYSTEM_LAT", "").strip()
    lon_raw = get_env("SYSTEM_LON", "").strip()
    if not lat_raw or not lon_raw:
        return None
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except ValueError:
        return None
    return {"lat": lat, "lon": lon, "source": "env"}

def get_system_position() -> dict[str, str | float] | None:
    """Holt die Position des Systems aus den Umgebungsvariablen.

    Rückgabe: {"lat": float, "lon": float, "source": str} oder None.
    """
    return _read_env_position()
