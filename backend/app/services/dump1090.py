from __future__ import annotations

"""
Client for dump1090's JSON data endpoint.

The Raspberry Pi backend polls dump1090 frequently and keeps a small in-memory cache.
This module focuses on:
- HTTP fetching with short timeouts
- Robust parsing (lat/lon may be missing; some fields may be non-numeric)
- Mapping raw JSON dicts to typed Pydantic models
"""

import time
from typing import Any

import httpx

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


class Dump1090Client:
    """Small async HTTP client for `aircraft.json`."""

    def __init__(self, url: str, timeout_s: float = 0.8) -> None:
        """
        Args:
            url: dump1090 endpoint (typically http://127.0.0.1:8080/data/aircraft.json)
            timeout_s: request timeout in seconds; keep small for responsive UI
        """
        self.url = url
        self._timeout = httpx.Timeout(timeout_s)

    async def fetch_aircraft(self) -> tuple[list[Aircraft], float]:
        """
        Fetch and parse the current aircraft list.

        Returns:
            (aircraft, polled_at_unix_s)
        """
        polled_at = time.time()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            payload = response.json()

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
                        altitude=_to_float(item.get("altitude")),
                        speed=_to_float(item.get("speed")),
                    )
                )

        return aircraft, polled_at
