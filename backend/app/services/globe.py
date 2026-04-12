from __future__ import annotations

"""
Globe forwarding integration.

The "globe" (ESP32 / microcontroller) protocol is intentionally modular and controlled
by environment variables so it can be changed without touching the UI or dump1090 code.

Supported modes:
- disabled: do nothing (useful during development)
- http: POST JSON to a configurable URL
- udp: send a JSON datagram to host:port
"""

import asyncio
import json
import socket
from typing import Any

import httpx

from ..models import Aircraft, GlobeForwardResult
from ..utils import get_env, get_env_float, get_env_int


def _aircraft_payload(aircraft: Aircraft) -> dict[str, Any]:
    """
    Create a small JSON-serializable payload for the globe.

    The globe is expected to primarily use lat/lon, but including extra fields helps
    debugging and allows richer visualizations later.
    """
    return {
        "hex": aircraft.hex,
        "flight": aircraft.flight,
        "lat": aircraft.lat,
        "lon": aircraft.lon,
        "altitude": aircraft.altitude,
        "speed": aircraft.speed,
    }


async def forward_to_globe(aircraft: Aircraft) -> GlobeForwardResult:
    """
    Forward an aircraft selection to the globe.

    Environment variables:
    - GLOBE_MODE: disabled | http | udp
    - GLOBE_HTTP_URL, GLOBE_HTTP_TIMEOUT_S
    - GLOBE_UDP_HOST, GLOBE_UDP_PORT
    """
    mode = get_env("GLOBE_MODE", "disabled").lower()

    if mode == "disabled":
        return GlobeForwardResult(mode=mode, sent=False, detail="globe forwarding disabled")

    if aircraft.lat is None or aircraft.lon is None:
        return GlobeForwardResult(mode=mode, sent=False, detail="aircraft has no position (lat/lon missing)")

    if mode == "http":
        url = get_env("GLOBE_HTTP_URL", "http://192.168.4.1/aircraft")
        timeout_s = get_env_float("GLOBE_HTTP_TIMEOUT_S", 1.0)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
                response = await client.post(url, json=_aircraft_payload(aircraft))
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                parsed: Any
                if "application/json" in content_type:
                    parsed = response.json()
                else:
                    parsed = response.text
            return GlobeForwardResult(mode=mode, sent=True, response=parsed)
        except Exception as exc:
            return GlobeForwardResult(mode=mode, sent=False, detail=str(exc))

    if mode == "udp":
        host = get_env("GLOBE_UDP_HOST", "192.168.4.1")
        port = get_env_int("GLOBE_UDP_PORT", 4210)
        message = json.dumps(_aircraft_payload(aircraft), separators=(",", ":")).encode("utf-8")

        def _send_udp() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(message, (host, port))

        try:
            await asyncio.to_thread(_send_udp)
            return GlobeForwardResult(mode=mode, sent=True, detail=f"sent {len(message)} bytes to {host}:{port}")
        except Exception as exc:
            return GlobeForwardResult(mode=mode, sent=False, detail=str(exc))

    return GlobeForwardResult(mode=mode, sent=False, detail=f"unknown GLOBE_MODE={mode!r}")
