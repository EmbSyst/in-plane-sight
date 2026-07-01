from __future__ import annotations

"""globe.py - MQTT-Publisher für den Holo-Globe.

Zuständig für die dauerhafte MQTT-Verbindung zum Broker und das Veröffentlichen von:
- Display-Modes
- Motor-PWM
- Set Points (Flugzeugpositionen)
"""

import asyncio
import json
import logging
import threading
from typing import Any

import paho.mqtt.client as mqtt

from ..models import Aircraft, GlobeForwardResult
from ..utils import get_env, get_env_int

logger = logging.getLogger("in-plane-sight.globe")

# Speichert den MQTT-Client-Zustand, um bei jedem Aufruf darauf zugreifen zu können.
_MQTT_CLIENT: mqtt.Client | None = None
_MQTT_LOCK = threading.Lock()


def _set_points_payload(aircraft: Aircraft) -> dict[str, Any]:
    """Erstellt eine 'set_points' Nachricht für das ausgewählte Flugzeug."""
    point_id = aircraft.flight.strip() if aircraft.flight and aircraft.flight.strip() else aircraft.hex
    return {
        "type": "set_points",
        "points": [
            {
                "id": point_id,
                "lat": aircraft.lat,
                "lon": aircraft.lon,
                "color": [255, 0, 0],
            }
        ]
    }


def _aircraft_payload(aircraft: Aircraft) -> dict[str, Any]:
    """
    Erstellt einen kleinen, JSON-serialisierbaren Payload für den Globe.

    Der Globe benötigt primär lat/lon, aber das Hinzufügen weiterer Felder
    hilft beim Debugging und ermöglicht später komplexere Visualisierungen.
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
    """Liest die MQTT-Verbindungseinstellungen aus den Umgebungsvariablen aus.
    
    Rückgabe: (host, port, topic, qos, retain, username, password)
    """
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
    """Wird beim App-Start aufgerufen, um die MQTT-Verbindung aufzubauen."""
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

        # Wir blockieren beim Verbindungsaufbau nicht (non-blocking connect im Hintergrund)
        try:
            client.connect_async(host, port, 60)
            client.loop_start()
        except Exception as exc:
            logger.warning("globe MQTT init failed; continuing without globe forwarding: %s", exc)
            return
        _MQTT_CLIENT = client


def shutdown_globe_transport() -> None:
    """Wird beim App-Shutdown aufgerufen, um die Verbindung sauber zu trennen."""
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
    """Veröffentlicht eine Liste von Payloads nacheinander auf dem konfigurierten Topic."""
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
    """Sendet eine Änderung des Anzeigemodus an den Globe."""
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
        
    # Wir haben MQTT-Payloads nur für diese neuen Modi in diesem Projekt spezifiziert
        return GlobeForwardResult(mode=globe_mode, sent=False, detail=f"Anzeigemodus für mode={globe_mode!r} nicht unterstützt")


async def publish_set_points(points: list[dict[str, Any]]) -> GlobeForwardResult:
    """Sendet beliebige Punkte (set_points) an den Globe."""
    globe_mode = get_env("GLOBE_MODE", "mqtt").lower()
    
    if globe_mode == "disabled":
        return GlobeForwardResult(mode=globe_mode, sent=False, detail="globe forwarding disabled")
        
    message = {
        "type": "set_points",
        "points": points,
    }
    
    if globe_mode == "mqtt":
        return await _publish_mqtt_messages([message])
        
    return GlobeForwardResult(mode=globe_mode, sent=False, detail=f"set points not supported for mode={globe_mode!r}")


def _rpm_to_pwm_values(mode: int, rpm: int | None) -> list[int]:
    """Wandelt den gewünschten Motormodus/RPM in eine Liste von Integern um, die der Pico erwartet.

    mode 0 = Motor aus -> leere Liste.
    mode 1 = Laufen -> Ziel-RPM als Int-Liste. Aktuell 1:1 durchgereicht;
    hier kann später eine echte RPM->PWM Umrechnung implementiert werden.
    """
    if mode == 0 or rpm is None:
        return []
    return [int(rpm)]


async def publish_change_pwm(mode: int, rpm: int | None = None) -> GlobeForwardResult:
    """Sendet eine Änderung der Motor-PWM (RPM) an den Globe/Pico."""
    globe_mode = get_env("GLOBE_MODE", "mqtt").lower()

    if globe_mode == "disabled":
        return GlobeForwardResult(mode=globe_mode, sent=False, detail="globe forwarding disabled")

    message = {
        "type": "change_PWM",
        "mode": mode,
        "rpm": _rpm_to_pwm_values(mode, rpm),
    }

    if globe_mode == "mqtt":
        return await _publish_mqtt_messages([message])

    return GlobeForwardResult(mode=globe_mode, sent=False, detail=f"change_PWM not supported for mode={globe_mode!r}")


async def forward_to_globe(aircraft: Aircraft) -> GlobeForwardResult:
    """
    Leitet ein ausgewähltes Flugzeug an den Globe weiter.

    Umgebungsvariablen:
    - GLOBE_MODE: disabled | mqtt
    - GLOBE_MQTT_HOST, GLOBE_MQTT_PORT, GLOBE_MQTT_TOPIC
    """
    mode = get_env("GLOBE_MODE", "mqtt").lower()

    if mode == "disabled":
        return GlobeForwardResult(mode=mode, sent=False, detail="globe forwarding disabled")

    if aircraft.lat is None or aircraft.lon is None:
        return GlobeForwardResult(mode=mode, sent=False, detail="aircraft has no position (lat/lon missing)")

    if mode == "mqtt":
        messages = [
            _set_points_payload(aircraft),
        ]
        return await _publish_mqtt_messages(messages)

    return GlobeForwardResult(mode=mode, sent=False, detail=f"unknown GLOBE_MODE={mode!r}")
