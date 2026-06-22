from __future__ import annotations

"""
Globe forwarding integration.

The transport is controlled by environment variables so it can evolve without touching
the UI or dump1090 code. The current preferred mode is MQTT, but legacy HTTP/UDP modes
are kept as fallback while the group transitions the Pico integration.
"""

import asyncio
import json
import socket
import threading
from typing import Any

import httpx
import paho.mqtt.client as mqtt

from ..models import Aircraft, GlobeForwardResult
from ..utils import get_env, get_env_int

_MQTT_CLIENT: mqtt.Client | None = None
_MQTT_LOCK = threading.Lock()

_MQTT_CLIENT: mqtt.Client | None = None
_MQTT_LOCK = threading.Lock()


def _display_mode_payload() -> dict[str, Any]:
    """Message that switches the globe into aircraft display mode."""
    return {
        "type": "change_display_mode",
        "mode": 2,
        "color": [255, 255, 255],
    }


def _plane_position_payload(aircraft: Aircraft) -> dict[str, Any]:
    """
    Message for positioning an aircraft on the globe.

    The final lat/lon -> x/y conversion is still pending, so this uses configurable
    dummy coordinates for now. This keeps the MQTT path testable while the mapping is
    still being defined by the team.
    """
    _ = aircraft
    return {
        "type": "change_plane_position",
        "x": get_env_int("GLOBE_DUMMY_X", 0),
        "y": get_env_int("GLOBE_DUMMY_Y", 0),
    }


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


def _mqtt_client_settings() -> tuple[str, int, str, int, bool, str | None, str | None]:
    return (
        get_env("GLOBE_MQTT_HOST", "test.mosquitto.org"),
        get_env_int("GLOBE_MQTT_PORT", 1883),
        get_env("GLOBE_MQTT_TOPIC", "in-plane-sight"),
        get_env_int("GLOBE_MQTT_QOS", 0),
        get_env("GLOBE_MQTT_RETAIN", "0").lower() in {"1", "true", "yes", "on"},
        get_env("GLOBE_MQTT_USERNAME", ""),
        get_env("GLOBE_MQTT_PASSWORD", ""),
    )


def init_globe_transport() -> None:
    """Initialize long-lived transport clients for the selected mode."""
    global _MQTT_CLIENT
    mode = get_env("GLOBE_MODE", "mqtt").lower()
    if mode != "mqtt":
        return

    with _MQTT_LOCK:
        if _MQTT_CLIENT is not None:
            return

        host, port, _topic, _qos, _retain, username, password = _mqtt_client_settings()
        client = mqtt.Client()
        if username:
            client.username_pw_set(username, password)
        client.connect(host, port, 60)
        client.loop_start()
        _MQTT_CLIENT = client


def shutdown_globe_transport() -> None:
    """Tear down any long-lived transport client cleanly."""
    global _MQTT_CLIENT
    with _MQTT_LOCK:
        client = _MQTT_CLIENT
        _MQTT_CLIENT = None

    if client is not None:
        try:
            client.loop_stop()
        finally:
            client.disconnect()


async def _publish_mqtt_messages(messages: list[dict[str, Any]]) -> GlobeForwardResult:
    def _publish() -> GlobeForwardResult:
        init_globe_transport()
        host, port, topic, qos, retain, _username, _password = _mqtt_client_settings()
        client = _MQTT_CLIENT
        if client is None:
            return GlobeForwardResult(mode="mqtt", sent=False, detail="mqtt client not initialized")

        for message in messages:
            payload = json.dumps(message, separators=(",", ":"))
            info = client.publish(topic, payload, qos=qos, retain=retain)
            if getattr(info, "rc", 0) != 0:
                return GlobeForwardResult(mode="mqtt", sent=False, detail=f"mqtt publish failed rc={info.rc}")

        return GlobeForwardResult(
            mode="mqtt",
            sent=True,
            detail=f"published {len(messages)} mqtt messages to {host}:{port}/{topic}",
            response=messages,
        )

    return await asyncio.to_thread(_publish)


async def publish_display_mode(mode: int, color: list[int] | None = None) -> GlobeForwardResult:
    """Publish a display mode change to the globe."""
    globe_mode = get_env("GLOBE_MODE", "mqtt").lower()
    
    if globe_mode == "disabled":
        return GlobeForwardResult(mode=globe_mode, sent=False, detail="globe forwarding disabled")
        
    if color is None:
        color = [255, 255, 255]
        
    message = {
        "type": "change_display_mode",
        "mode": mode,
        "color": color,
    }
    
    if globe_mode == "mqtt":
        return await _publish_mqtt_messages([message])
        
    # We only implemented MQTT payload specs for these new modes in this project
    return GlobeForwardResult(mode=globe_mode, sent=False, detail=f"display mode change not supported for mode={globe_mode!r}")


async def forward_to_globe(aircraft: Aircraft) -> GlobeForwardResult:
    """
    Forward an aircraft selection to the globe.

    Environment variables:
    - GLOBE_MODE: disabled | mqtt | http | udp
    - GLOBE_HTTP_URL, GLOBE_HTTP_TIMEOUT_S
    - GLOBE_UDP_HOST, GLOBE_UDP_PORT
    - GLOBE_MQTT_HOST, GLOBE_MQTT_PORT, GLOBE_MQTT_TOPIC
    """
    mode = get_env("GLOBE_MODE", "mqtt").lower()

    if mode == "disabled":
        return GlobeForwardResult(mode=mode, sent=False, detail="globe forwarding disabled")

    if aircraft.lat is None or aircraft.lon is None:
        return GlobeForwardResult(mode=mode, sent=False, detail="aircraft has no position (lat/lon missing)")

    if mode == "mqtt":
        messages = [
            _display_mode_payload(),
            _plane_position_payload(aircraft),
        ]
        return await _publish_mqtt_messages(messages)

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

        messages = [
            _display_mode_payload(),
            _plane_position_payload(aircraft),
        ]

        def _publish() -> GlobeForwardResult:
            client = _get_or_create_mqtt_client()
            for message in messages:
                payload = json.dumps(message, separators=(",", ":"))
                info = client.publish(topic, payload, qos=qos, retain=retain)
                if getattr(info, "rc", 0) != 0:
                    return GlobeForwardResult(mode=mode, sent=False, detail=f"mqtt publish failed rc={info.rc}")
            return GlobeForwardResult(
                mode=mode,
                sent=True,
                detail=f"published {len(messages)} mqtt messages to {host}:{port}/{topic}",
                response=messages,
            )

        try:
            return await asyncio.to_thread(_publish)
        except Exception as exc:
            return GlobeForwardResult(mode=mode, sent=False, detail=str(exc))

    return GlobeForwardResult(mode=mode, sent=False, detail=f"unknown GLOBE_MODE={mode!r}")
