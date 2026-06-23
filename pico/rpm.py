"""rpm.py - Hall-IRQ misst Drehperiode/Phase und schreibt sie in state.

NORMALER (soft) IRQ - NICHT hard=True (sonst MemoryError bei Allokation).
Der Pin wird in einer Modul-Variable festgehalten, sonst raeumt der GC die
IRQ-Registrierung weg.

Messlogik:
  - ROHE letzte Periode (kein EMA) -> RPM springt sofort auf den echten Wert.
  - Mikrosekunden -> feine POV-Phase.
  - Beidseitiger Ausreisser-Schutz: ein Abstand kleiner als die halbe oder
    groesser als die doppelte laufende Periode ist fast immer ein Stoerpuls ->
    verwerfen, OHNE die Referenz zu verschieben (der naechste echte Puls misst
    dann korrekt vom letzten guten Rand). Es werden aber hoechstens
    HALL_MAX_SKIP Pulse am Stueck verworfen -> kann sich NIE festklemmen.
"""

import time
from machine import Pin

import config
import state

_hall_pin = None        # Pin festhalten, sonst stirbt die IRQ-Registrierung beim GC
_skip = 0               # wie viele unplausible Pulse zuletzt am Stueck verworfen wurden


def _hall_irq(pin):
    global _skip
    now = time.ticks_us()
    last = state.last_pulse_us
    if last == 0:                                 # erster Puls: nur Referenz setzen
        state.last_pulse_us = now
        return
    dt = time.ticks_diff(now, last)
    if dt < config.MIN_PERIOD_US:                 # harte Prell-Grenze -> ignorieren
        return
    p = state.period_us
    # < halbe oder > doppelte Periode = Stoerpuls -> verwerfen (Referenz behalten),
    # aber nie mehr als HALL_MAX_SKIP am Stueck (sonst Festklemmen).
    if p and _skip < config.HALL_MAX_SKIP and (dt < (p >> 1) or dt > (p << 1)):
        _skip += 1
        return
    _skip = 0
    state.last_pulse_us = now                     # echte Flanke -> Phase aktualisieren
    state.seq += 1
    state.period_us = dt                          # rohe letzte Umdrehung


def init():
    global _hall_pin
    _hall_pin = Pin(config.HALL_PIN, Pin.IN, Pin.PULL_UP)
    # Soft IRQ (kein hard=True!) -> Allokation erlaubt, kein MemoryError.
    _hall_pin.irq(trigger=Pin.IRQ_FALLING, handler=_hall_irq)
