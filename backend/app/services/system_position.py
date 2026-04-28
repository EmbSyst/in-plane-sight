from __future__ import annotations

"""
System position provider (lat/lon) for distance calculations.

The frontend can compute the distance between the system (RasPi) and a selected
aircraft if the backend exposes the system's own position.

Sources (in priority order):
1) Environment variables SYSTEM_LAT and SYSTEM_LON
2) GPSD (if available) via a lightweight TCP JSON watch

The function returns a small dict to keep dependencies minimal.
"""

import json
import socket
import time
from typing import Any

from ..utils import get_env, get_env_float

_CACHE_TTL_S = 2.0
_cached_at_unix_s: float | None = None
_cached_value: dict[str, Any] | None = None


def _get_cached(now_unix_s: float) -> dict[str, Any] | None:
    if _cached_at_unix_s is None or _cached_value is None:
        return None
    if now_unix_s - _cached_at_unix_s > _CACHE_TTL_S:
        return None
    return _cached_value


def _set_cached(now_unix_s: float, value: dict[str, Any] | None) -> None:
    global _cached_at_unix_s, _cached_value
    _cached_at_unix_s = now_unix_s
    _cached_value = value


def clear_system_position_cache() -> None:
    """Clear the small in-memory cache (useful for tests)."""
    global _cached_at_unix_s, _cached_value
    _cached_at_unix_s = None
    _cached_value = None


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


def _read_gpsd_position() -> dict[str, Any] | None:
    host = get_env("GPSD_HOST", "127.0.0.1")
    port = int(get_env_float("GPSD_PORT", 2947))
    timeout_s = get_env_float("GPSD_TIMEOUT_S", 0.6)

    try:
        with socket.create_connection((host, port), timeout=timeout_s) as s:
            s.settimeout(timeout_s)
            s.sendall(b'?WATCH={"enable":true,"json":true};\n')
            buf = b""
            end_at = time.time() + timeout_s
            while time.time() < end_at:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    if obj.get("class") != "TPV":
                        continue
                    lat = obj.get("lat")
                    lon = obj.get("lon")
                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                        return {"lat": float(lat), "lon": float(lon), "source": "gpsd"}
    except Exception:
        return None

    return None


def get_system_position() -> dict[str, Any] | None:
    """
    Return the system's current position as {"lat": float, "lon": float, "source": str}.

    The result is cached briefly to avoid hitting GPSD on every API poll.
    """
    now = time.time()
    cached = _get_cached(now)
    if cached is not None:
        return cached

    value = _read_env_position()
    if value is None:
        value = _read_gpsd_position()

    _set_cached(now, value)
    return value
