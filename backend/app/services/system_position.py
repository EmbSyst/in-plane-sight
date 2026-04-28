from __future__ import annotations

"""
System position provider (lat/lon) for distance calculations.

The frontend can compute the distance between the system (RasPi) and a selected
aircraft if the backend exposes the system's own position.

Sources (in priority order):
1) Environment variables SYSTEM_LAT and SYSTEM_LON
2) (removed) GPSD / GeoIP fallbacks

The function returns a small dict to keep dependencies minimal.
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

def get_system_position() -> dict[str, Any] | None:
    """
    Return the system's current position as {"lat": float, "lon": float, "source": str}.
    """
    return _read_env_position()
