import json
import socket
import time

import network
import neopixel
from machine import Pin

WIFI_SSID = "Olymp Bietigheim"
WIFI_PASSWORD = "Olymp_Bietigheim4j6nzhRpscsx!"

UDP_PORT = 5005
LED_PIN = 18
NUM_LEDS = 6
BPP = 4


def set_all(pixels, r, g, b, w=0):
    for i in range(NUM_LEDS):
        pixels[i] = (r, g, b, w)
    pixels.write()


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if WIFI_SSID:
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(25):
            if wlan.isconnected():
                break
            time.sleep(0.4)
    return wlan


def main():
    pixels = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), NUM_LEDS, bpp=BPP)
    set_all(pixels, 0, 0, 0, 0)

    wlan = connect_wifi()
    if wlan.isconnected():
        set_all(pixels, 0, 0, 32, 0)
        print("wifi:", wlan.ifconfig())
    else:
        set_all(pixels, 32, 0, 0, 0)
        print("wifi not connected")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    print("udp listening on", sock.getsockname())
    set_all(pixels, 0, 16, 0, 0)

    while True:
        data, addr = sock.recvfrom(2048)
        print("from", addr, "len", len(data))
        try:
            obj = json.loads(data.decode("utf-8"))
        except Exception:
            set_all(pixels, 64, 0, 0, 0)
            continue

        if isinstance(obj, dict) and obj.get("type") == "color":
            r = int(obj.get("r", 0))
            g = int(obj.get("g", 0))
            b = int(obj.get("b", 0))
            w = int(obj.get("w", 0))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            w = max(0, min(255, w))
            set_all(pixels, r, g, b, w)
        else:
            set_all(pixels, 0, 64, 0, 0)


main()
