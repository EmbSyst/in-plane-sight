"""pintest.py - testet nur den Signal-Pin von Arm B (config.DATA_PIN_B).

Schaltet den GPIO im 1-Sekunden-Takt HIGH/LOW (1/0) - kein neopixel, nur roher
Pin-Pegel. Mit Multimeter / Logic-Analyzer / LED gegen GND messen.

Run in Thonny (Strg-C stoppt).
"""

import time
from machine import Pin

import config

pin = Pin(config.DATA_PIN_B, Pin.OUT)

print("Test Signal-Pin GP%d (Arm B) - Strg-C zum Stoppen" % config.DATA_PIN_B)
while True:
    pin.value(1)
    print("1 (HIGH)")
    time.sleep(100)
    pin.value(0)
    print("0 (LOW)")
    time.sleep(1)
