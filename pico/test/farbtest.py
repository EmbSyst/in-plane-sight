"""farbtest.py - kleiner LED-Farbtest fuer den SK6812(W)-Aufbau.

Laesst BEIDE Streifen nacheinander in mehreren Farben leuchten, jede 3 Sekunden,
dann von vorne. Nutzt Pins / LED-Zahl / bpp aus config.py. Kein Drehen, kein
Framebuffer noetig.

Benutzung: config.py + farbtest.py auf den Pico, dann farbtest.py in Thonny
'Run' (oder als main.py kopieren). Strg-C stoppt.
"""

import time
import neopixel
from machine import Pin

import config

LEVEL = 80   # Helligkeit 0..255 (RGBW-Weiss zieht viel Strom -> moderat halten)

L = LEVEL
FARBEN = [                       # (Name, (R, G, B, W))
    ("Rot",      (L, 0, 0, 0)),
    ("Gruen",    (0, L, 0, 0)),
    ("Blau",     (0, 0, L, 0)),
    ("Gelb",     (L, L, 0, 0)),
    ("Cyan",     (0, L, L, 0)),
    ("Magenta",  (L, 0, L, 0)),
    ("Weiss (W)",(0, 0, 0, L)),  # echtes Weiss ueber die W-LED
    ("Aus",      (0, 0, 0, 0)),
]

np_a = neopixel.NeoPixel(Pin(config.DATA_PIN_A), config.LEDS_PER_ARM,
                         bpp=config.BYTES_PER_LED)
np_b = neopixel.NeoPixel(Pin(config.DATA_PIN_B), config.LEDS_PER_ARM,
                         bpp=config.BYTES_PER_LED)


def fuelle(rgbw):
    color = rgbw[:config.BYTES_PER_LED]   # bei reinem RGB-Streifen faellt W weg
    for i in range(config.LEDS_PER_ARM):
        np_a[i] = color
        np_b[i] = color
    np_a.write()
    np_b.write()


print("Farbtest laeuft - Strg-C zum Stoppen")
while True:
    for name, rgbw in FARBEN:
        print(name)
        fuelle(rgbw)
        time.sleep(3)
