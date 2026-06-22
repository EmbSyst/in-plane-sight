import json
import time

import network
import neopixel
from machine import Pin
from umqtt.simple import MQTTClient

WIFI_SSID = ""
WIFI_PASSWORD = ""
WIFI_TIMEOUT_S = 20

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_CLIENT_ID = b"in-plane-sight-pico"
MQTT_TOPIC = b"in-plane-sight"

LED_PIN = 18
NUM_LEDS = 6
BPP = 4


def set_all(pixels, r, g, b, w=0):
    for i in range(NUM_LEDS):
        pixels[i] = (r, g, b, w)
    pixels.write()


def connect_wifi():
    if not WIFI_SSID:
        raise RuntimeError("WIFI_SSID not set")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan

    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > WIFI_TIMEOUT_S:
            raise RuntimeError("wifi timeout")
        time.sleep(0.5)
    return wlan


def main():
    pixels = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), NUM_LEDS, bpp=BPP)
    set_all(pixels, 0, 0, 0, 0)

    wlan = connect_wifi()
    set_all(pixels, 0, 0, 32, 0)
    print("wifi:", wlan.ifconfig())

    def on_msg(topic, msg):
        print("topic:", topic)
        print("msg:", msg)
        try:
            obj = json.loads(msg)
        except Exception:
            set_all(pixels, 64, 0, 0, 0)
            return

        if not isinstance(obj, dict):
            return

        t = obj.get("type")
        if t == "change_display_mode":
            color = obj.get("color") or [255, 255, 255]
            try:
                r, g, b = int(color[0]), int(color[1]), int(color[2])
            except Exception:
                r, g, b = 255, 255, 255
            set_all(pixels, max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), 0)
        elif t == "change_plane_position":
            set_all(pixels, 0, 64, 0, 0)
        elif t == "change_PWM":
            set_all(pixels, 0, 0, 64, 0)

    while True:
        try:
            client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, keepalive=60)
            client.set_callback(on_msg)
            client.connect()
            client.subscribe(MQTT_TOPIC)
            print("subscribed:", MQTT_TOPIC)
            set_all(pixels, 0, 16, 0, 0)

            while True:
                client.check_msg()
                time.sleep(0.2)
        except Exception as exc:
            print("mqtt loop failed:", exc)
            set_all(pixels, 64, 0, 0, 0)
            time.sleep(3)


main()
