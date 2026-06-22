from __future__ import annotations

"""
Globe forwarding integration.

The forwarding layer is controlled by environment variables.

Supported modes:
- disabled: do nothing (useful during development)
- mqtt: publish JSON messages to an MQTT broker (current default)
"""

import asyncio
import json
import threading
from typing import Any

import paho.mqtt.client as mqtt

from ..models import Aircraft, GlobeForwardResult
from ..utils import get_env, get_env_int

_MQTT_CLIENT: mqtt.Client | None = None
_MQTT_LOCK = threading.Lock()


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


def _display_mode_payload() -> dict[str, Any]:
    return {"type": "change_display_mode", "mode": 2, "color": [255, 255, 255]}


def _plane_position_payload(_aircraft: Aircraft) -> dict[str, Any]:
    return {
        "type": "change_plane_position",
        "x": get_env_int("GLOBE_DUMMY_X", 0),
        "y": get_env_int("GLOBE_DUMMY_Y", 0),
    }


def _mqtt_settings() -> tuple[str, int, str, int, bool, str, str]:
    host = get_env("GLOBE_MQTT_HOST", "test.mosquitto.org")
    port = get_env_int("GLOBE_MQTT_PORT", 1883)
    topic = get_env("GLOBE_MQTT_TOPIC", "in-plane-sight")
    qos = get_env_int("GLOBE_MQTT_QOS", 0)
    retain = get_env("GLOBE_MQTT_RETAIN", "0").lower() in {"1", "true", "yes", "on"}
    username = get_env("GLOBE_MQTT_USERNAME", "")
    password = get_env("GLOBE_MQTT_PASSWORD", "")
    return host, port, topic, qos, retain, username, password


def _get_or_create_mqtt_client() -> mqtt.Client:
    global _MQTT_CLIENT
    with _MQTT_LOCK:
        if _MQTT_CLIENT is not None:
            return _MQTT_CLIENT

        host, port, _topic, _qos, _retain, username, password = _mqtt_settings()
        client = mqtt.Client()
        if username:
            client.username_pw_set(username, password)
        client.connect(host, port, 60)
        client.loop_start()
        _MQTT_CLIENT = client
        return client


def shutdown_globe_transport() -> None:
    global _MQTT_CLIENT
    with _MQTT_LOCK:
        client = _MQTT_CLIENT
        _MQTT_CLIENT = None

    if client is not None:
        try:
            client.loop_stop()
        finally:
            client.disconnect()


async def forward_to_globe(aircraft: Aircraft) -> GlobeForwardResult:
    """
    Forward an aircraft selection to the globe.

    Environment variables:
    - GLOBE_MODE: disabled | mqtt
    - GLOBE_MQTT_HOST, GLOBE_MQTT_PORT, GLOBE_MQTT_TOPIC
    - GLOBE_MQTT_QOS, GLOBE_MQTT_RETAIN
    - GLOBE_DUMMY_X, GLOBE_DUMMY_Y
    """
    mode = get_env("GLOBE_MODE", "mqtt").lower()

    if mode == "disabled":
        return GlobeForwardResult(mode=mode, sent=False, detail="globe forwarding disabled")

    if aircraft.lat is None or aircraft.lon is None:
        return GlobeForwardResult(mode=mode, sent=False, detail="aircraft has no position (lat/lon missing)")

    if mode == "mqtt":
        host, port, topic, qos, retain, _username, _password = _mqtt_settings()

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
