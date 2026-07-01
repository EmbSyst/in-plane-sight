from __future__ import annotations

"""dump1090.py - File-Reader für dump1090-fa JSON Snapshots.

Liest und parst die lokale Datei aircraft.json.
"""

import json
import time
from typing import Any

from ..models import Aircraft


def _clean_str(value: Any) -> str | None:
    """Normalisiert String-Felder: umwandeln in str, Leerzeichen entfernen, gibt None zurück wenn leer."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float | None:
    """Wandelt Werte in Floats um, gibt None zurück bei ungültigen/fehlenden Eingaben."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_float(item: dict[str, Any], keys: list[str]) -> float | None:
    """Sucht in einem Dictionary nach dem ersten gültigen Float-Wert für eine Liste von Schlüsseln."""
    for key in keys:
        value = _to_float(item.get(key))
        if value is not None:
            return value
    return None


class Dump1090Client:
    """Kapselt das Auslesen und Parsen der lokalen aircraft.json."""

    def __init__(self, file_path: str) -> None:
        """
        Args:
            file_path: Pfad zum dump1090 Aircraft-Snapshot (normalerweise /tmp/aircraft.json)
        """
        self.file_path = file_path

    async def fetch_aircraft(self) -> tuple[list[Aircraft], float]:
        """
        Liest und parst die aktuelle Flugzeugliste.

        Rückgabe:
            (aircraft, polled_at_unix_s)
        """
        polled_at = time.time()
        payload = self._read_payload()

        raw_list = payload.get("aircraft", [])
        aircraft: list[Aircraft] = []

        if isinstance(raw_list, list):
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                hex_id = _clean_str(item.get("hex"))
                if not hex_id:
                    continue
                aircraft.append(
                    Aircraft(
                        hex=hex_id,
                        flight=_clean_str(item.get("flight")),
                        lat=_to_float(item.get("lat")),
                        lon=_to_float(item.get("lon")),
                        altitude=_first_float(item, ["altitude", "alt_baro", "alt_geom"]),
                        speed=_first_float(item, ["speed", "gs", "tas"]),
                    )
                )

        return aircraft, polled_at

    def _read_payload(self) -> dict[str, Any]:
        """
        Liest den lokalen dump1090 JSON-Payload von der Festplatte.

        Fallback: leere Liste zurückgeben, falls die Datei noch nicht geschrieben wurde
        oder gerade von dump1090 überschrieben wird (FileNotFoundError / JSONDecodeError).
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"aircraft": []}
        except json.JSONDecodeError:
            return {"aircraft": []}
