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
_hist = []              # letzte rohe Perioden fuer den Median (service(), nicht im IRQ!)
_last_seq = -1          # letzte von service() verarbeitete Umdrehung


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
    # Ausreisser-Schutz gegen den letzten ROHWERT (Original-Verhalten, stabil &
    # selbstkorrigierend). KEINE Rueckkopplung von period_filt in den IRQ: das
    # fuehrte zum Boot-Deadlock (period_filt seedet langsam -> echte schnellere
    # Pulse fallen aus dem Fenster -> werden abgelehnt -> period_filt bleibt
    # haengen -> Anzeige eingefroren). Die Glaettung passiert downstream im Median
    # (state.period_filt), den NUR Anzeige + Log nutzen.
    # (dt>>1) > p : dt > ~2*p (zu lang);  (p>>1) > dt : dt < ~p/2 (Stoerflanke)
    p = state.period_us
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


def service():
    """Pro Hauptschleifen-Runde aufrufen (nicht-blockierend). Bildet bei jeder
    neuen Umdrehung den Median der letzten N rohen Perioden und legt ihn in
    state.period_filt ab - genutzt von Anzeige und Log (NICHT vom Hall-IRQ; der
    prueft gegen den Rohwert, sonst Boot-Deadlock / eingefrorene Anzeige).
    Median statt Mittelwert: einzelne 1000er-Spikes verschieben ihn nicht.
    Laeuft im Normalkontext (Sortieren/Allokation hier erlaubt, im IRQ nicht)."""
    global _last_seq
    if state.seq == _last_seq:                    # nur bei neuer Umdrehung neu rechnen
        return
    _last_seq = state.seq
    p = state.period_us
    if p <= 0:
        return
    _hist.append(p)
    if len(_hist) > config.PERIOD_MEDIAN_N:
        _hist.pop(0)
    state.period_filt = sorted(_hist)[len(_hist) // 2]
