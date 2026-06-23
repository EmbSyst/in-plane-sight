"""main.py - Dirigent fuer den SK6812-Test.

Laedt den Framebuffer aus dem Flash und gibt ihn synchron zur Drehung aus.
Kooperative Hauptschleife: jedes Modul bekommt pro Runde kurz das Wort.
MQTT (netz.py) ist in diesem Test bewusst deaktiviert.
"""

import gc
import struct
import time

import config
import state
import rpm
import motor
import display
import netz


def load_framebuffer(path):
    """Liest framebuffer.bin, prueft den Header gegen config und liefert die
    reinen Pixeldaten (ohne 16-Byte-Header) als memoryview zurueck."""
    with open(path, "rb") as f:
        data = f.read()
    magic, version, cols, leds, bpl, bright = struct.unpack("<4sBHHBB", data[:11])
    if magic != b"POVG":
        raise ValueError("keine POVG-Datei: %s" % path)
    if leds != config.NUM_LEDS or bpl != config.BYTES_PER_LED:
        raise ValueError(
            "Framebuffer (%d LEDs, %d B/LED) passt nicht zu config "
            "(%d LEDs, %d B/LED) -> neu rendern!"
            % (leds, bpl, config.NUM_LEDS, config.BYTES_PER_LED))
    return memoryview(data)[16:], cols, leds


def main():
    rpm.init()
    mot = motor.Motor()
    disp = display.Display()
    netz.init()

    pixels, cols, leds = load_framebuffer(config.FRAMEBUFFER_FILE)
    disp.set_framebuffer(pixels, cols, leds)
    print("Framebuffer geladen: %d Spalten x %d LEDs" % (cols, leds))

    last_seq = -1
    last_print = time.ticks_ms()
    while True:
        disp.service()              # zeitkritisch -> zuerst
        mot.service()
        netz.service()
        if state.seq != last_seq:    # GC in die Totzeit: einmal pro Umdrehung
            last_seq = state.seq
            gc.collect()

        # --- RPM-/Motor-Log alle 500 ms (wie im alten Test) ---
        if time.ticks_diff(time.ticks_ms(), last_print) >= 500:
            last_print = time.ticks_ms()
            prozent = state.duty / 65535 * 100
            if state.period_us > 0:
                rundzeit_ms = state.period_us / 1000
                drehzahl = 60000000 / state.period_us
                print("Motor: %.0f%%   RPM: %.0f   Rundzeit: %.1f ms"
                      % (prozent, drehzahl, rundzeit_ms))
            else:
                print("Motor: %.0f%%   Warte auf Hall-Signal..." % prozent)


main()
