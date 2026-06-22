"""
MicroPython entrypoint for the Pico.

- Connects to Wi-Fi on boot
- Connects to the public MQTT broker
- Subscribes to the shared topic used by the backend
- Keeps reconnecting if Wi-Fi or MQTT drops

Before uploading this file to the Pico, set WIFI_SSID and WIFI_PASSWORD locally.
Do not commit real credentials to git.
"""

import json
import time

import network
from umqtt.simple import MQTTClient
from wlanZugriff import *

try:
    import machine
except ImportError:  # pragma: no cover - MicroPython provides this on device
    machine = None

"""
WIFI_SSID = ""
WIFI_PASSWORD = ""
"""
WIFI_TIMEOUT_S = 30

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_CLIENT_ID = b"in-plane-sight-pico"
MQTT_TOPIC = b"in-plane-sight"
MQTT_KEEPALIVE_S = 60
MQTT_RETRY_DELAY_S = 5

DISPLAY_MODE_LIST = ["AUS", "EINE_FARBE", "UNUSED", "REGENBOGEN"]


def _reset_after_delay(delay_s):
    """Reset the Pico after a delay if machine.reset is available."""
    print("Reset in", delay_s, "seconds")
    time.sleep(delay_s)
    if machine is not None:
        machine.reset()
    raise RuntimeError("reset requested but machine.reset unavailable")



def handle_message(topic, raw_message):
    """Parse and handle one incoming MQTT message."""
    print("Message received on topic:", topic)
    print("Raw payload:", raw_message)

    try:
        message = json.loads(raw_message)
    except Exception as exc:
        print("JSON parse failed:", exc)
        return

    msg_type = message.get("type")
    if msg_type == "change_display_mode":
        mode = int(message.get("mode", -1))
        color = message.get("color", [255, 255, 255])
        if 0 <= mode < len(DISPLAY_MODE_LIST):
            print("Display mode ->", DISPLAY_MODE_LIST[mode], "color =", color)
        else:
            print("Invalid display mode:", mode)
    elif msg_type == "change_PWM":
        print("PWM update -> mode:", message.get("mode"), "rpm:", message.get("rpm"))
    elif msg_type == "set_points":
        points = message.get("points", [])
        print("Set points ->", len(points), "points")
        for p in points:
            print("  - id:", p.get("id"), "lat:", p.get("lat"), "lon:", p.get("lon"), "color:", p.get("color"))
    else:
        print("Unknown message type:", msg_type)


def mqtt_loop():
    """Maintain one MQTT connection and process messages until it fails."""
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        keepalive=MQTT_KEEPALIVE_S,
    )
    client.set_callback(handle_message)

    print("Connecting to MQTT broker:", MQTT_BROKER, "port", MQTT_PORT)
    client.connect()
    client.subscribe(MQTT_TOPIC)
    print("Subscribed to topic:", MQTT_TOPIC)

    try:
        while True:
            client.check_msg()
            time.sleep(0.2)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def main():
    """Boot entrypoint with reconnect loop for Wi-Fi and MQTT."""
    while True:
        try:
            connect_to_wlan()
            mqtt_loop()
        except Exception as exc:
            print("Connection loop failed:", exc)
            print("Retrying in", MQTT_RETRY_DELAY_S, "seconds")
            time.sleep(MQTT_RETRY_DELAY_S)


main()
