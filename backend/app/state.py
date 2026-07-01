from __future__ import annotations

"""state.py - gemeinsamer Zustand ('Whiteboard'). Nur Daten, keine Logik.

Beinhaltet In-Memory-Klassen, die den Zustand über Request-Grenzen hinweg teilen.
"""

import asyncio
from dataclasses import dataclass, field

from .models import Aircraft


@dataclass
class Dump1090State:
    """Speichert die neuesten dump1090-Abfrageergebnisse und den Fehlerstatus."""

    source_file_path: str
    poll_interval_s: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    # Flugzeugdaten
    aircraft: list[Aircraft] = field(default_factory=list)
    polled_at_unix_s: float | None = None
    error: str | None = None
    
    # Selektionsstatus für Live-MQTT-Publishing
    selected_hex: str | None = None
    # speichert (lat, lon, altitude, speed), um Änderungen zu erkennen
    last_forwarded_signature: tuple[float | None, float | None, float | None, float | None] | None = None
