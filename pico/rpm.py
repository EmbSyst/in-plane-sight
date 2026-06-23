"""rpm.py - Hall-IRQ misst Drehperiode/Phase und schreibt sie in state.

HARD IRQ: Zeitstempel exakt an der Flanke (immun gegen Schleifen-Verzoegerung
durch LED-DMA / netz / print / gc). Damit der hard IRQ NICHT abbricht:
  - keine Allokation: nur kleine Integer, nur Shifts (kein '*'/Big-Int),
  - KEINE config-Zugriffe im Handler -> die Konstanten werden in init() einmal
    gecached. (Sonst kracht es im IRQ, wenn config nicht zur rpm.py passt.)
  - Pin in Modul-Variable festhalten, sonst raeumt der GC die IRQ-Registrierung weg.

Messlogik:
  - rohe letzte Periode (kein EMA) -> RPM sofort korrekt.
  - beidseitiger Ausreisser-Schutz (kleiner als halbe / groesser als doppelte
    Periode = Stoerpuls -> verwerfen, Referenz behalten), aber hoechstens
    _max_skip am Stueck -> kann sich nie festklemmen.
"""

import time
from machine import Pin

import config
import state

_hall_pin = None        # Pin festhalten, sonst stirbt die IRQ-Registrierung beim GC
_skip = 0               # wie viele unplausible Pulse zuletzt am Stueck verworfen wurden
_min_period = 10000     # in init() aus config gesetzt (kein config-Zugriff im IRQ!)
_max_skip = 3


def _hall_irq(pin):
    global _skip
    now = time.ticks_us()
    last = state.last_pulse_us
    if last == 0:                                 # erster Puls: nur Referenz setzen
        state.last_pulse_us = now
        return
    dt = time.ticks_diff(now, last)
    if dt < _min_period:                          # Prellen -> ignorieren
        return
    p = state.period_us
    # Nur Shifts -> nie ein heap-allokierter Big-Int (hard-IRQ-sicher).
    # (dt >> 1) > p : dt groesser ~2*p (zu langsam);  (p >> 1) > dt : dt < ~p/2 (zu schnell)
    if p and _skip < _max_skip and ((dt >> 1) > p or (p >> 1) > dt):
        _skip += 1
        return
    _skip = 0
    state.last_pulse_us = now                     # echte Flanke -> Phase aktualisieren
    state.seq += 1
    state.period_us = dt                          # rohe letzte Umdrehung


def init():
    global _hall_pin, _min_period, _max_skip
    _min_period = config.MIN_PERIOD_US            # einmal cachen (im Normal-Kontext)
    _max_skip = config.HALL_MAX_SKIP
    _hall_pin = Pin(config.HALL_PIN, Pin.IN, Pin.PULL_UP)
    # hard=True: Zeitstempel exakt an der Flanke, immun gegen Schleifen-Verzoegerung.
    _hall_pin.irq(trigger=Pin.IRQ_FALLING, handler=_hall_irq, hard=True)
