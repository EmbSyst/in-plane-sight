from __future__ import annotations

"""
Client for dump1090's locally written JSON snapshot file.

The Raspberry Pi backend polls `/tmp/aircraft.json` frequently and keeps a small
in-memory cache.
This module focuses on:
- local file I/O with graceful error handling while dump1090 writes updates
- Robust parsing (lat/lon may be missing; some fields may be non-numeric)
- Mapping raw JSON dicts to typed Pydantic models
"""

import json
import time
from typing import Any

from ..models import Aircraft


def _clean_str(value: Any) -> str | None:
    """Normalize string-like fields: convert to str, strip, return None if empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float | None:
    """Convert values to float when possible, returning None for invalid/missing inputs."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(item: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = _to_float(item.get(key))
        if value is not None:
            return value
    return None


class Dump1090Client:
    """Small reader for the local dump1090 aircraft snapshot file."""

    def __init__(self, file_path: str) -> None:
        """
        Args:
            file_path: path to dump1090 aircraft snapshot (usually /tmp/aircraft.json)
        """
        self.file_path = file_path

    async def fetch_aircraft(self) -> tuple[list[Aircraft], float]:
        """
        Fetch and parse the current aircraft list.

        Returns:
            (aircraft, polled_at_unix_s)
        """
        polled_at = time.time()
        payload = self._read_payload()

        raw_list = payload.get("aircraft", [])
        aircraft: list[Aircraft] = []

        if isinstance(raw_list, list):
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                hex_id = _clean_str(item.get("hex"))
                if not hex_id:
                    continue
                aircraft.append(
                    Aircraft(
                        hex=hex_id,
                        flight=_clean_str(item.get("flight")),
                        lat=_to_float(item.get("lat")),
                        lon=_to_float(item.get("lon")),
                        altitude=_first_float(item, ["altitude", "alt_baro", "alt_geom"]),
                        speed=_first_float(item, ["speed", "gs", "tas"]),
                    )
                )

        return aircraft, polled_at

    def _read_payload(self) -> dict[str, Any]:
        """
        Read local dump1090 JSON payload from disk.

        If the file does not exist yet or is temporarily incomplete while being written,
        return an empty aircraft list instead of raising an exception.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"aircraft": []}
        except json.JSONDecodeError:
            return {"aircraft": []}
