"""
API-Level Tests für die FastAPI-Anwendung.

Diese Tests sind zur Laufzeit optional: Wenn FastAPI/Starlette in der aktuellen
Umgebung nicht installiert sind, werden die Tests übersprungen anstatt fehlzuschlagen.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock


class TestApiEndpoints(unittest.TestCase):
    def _imports_or_skip(self):
        try:
            from starlette.testclient import TestClient  # type: ignore
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"starlette TestClient ist nicht verfügbar: {exc}")

        try:
            from backend.app.main import create_app
            from backend.app.models import Aircraft
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"backend app Abhängigkeiten sind nicht verfügbar: {exc}")

        return TestClient, create_app, Aircraft

    def test_health(self) -> None:
        TestClient, create_app, _Aircraft = self._imports_or_skip()
        with mock.patch.dict(os.environ, {"GLOBE_MODE": "disabled"}, clear=False):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/api/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "ok"})

    def test_aircraft_list_reflects_cache(self) -> None:
        TestClient, create_app, Aircraft = self._imports_or_skip()
        with mock.patch.dict(os.environ, {"GLOBE_MODE": "disabled"}, clear=False):
            app = create_app()

            sample = [Aircraft(hex="abc123", flight="TEST123", lat=1.0, lon=2.0, altitude=1000, speed=250)]
            state = app.state.dump1090
        
        # Wenn der TestClient(app) erstellt wird, wird das 'startup' Event ausgelöst, was den Background Poller startet.
        # Wir müssen den Zustand *nach* dem Start des Clients setzen, oder den Task abbrechen, damit er ihn nicht überschreibt.
        # Alternativ mocken wir den Fetcher oder überschreiben die State Properties innerhalb des Blocks.
        
            with TestClient(app) as client, mock.patch.dict(
                os.environ,
                {"SYSTEM_LAT": "49.121479", "SYSTEM_LON": "9.211960"},
                clear=False,
            ):
                # Den Background Poller abbrechen, damit er unsere Mock-Daten nicht
                # mit Verbindungsfehlern überschreibt (da dump1090 nicht wirklich läuft)
                if app.state.poll_task:
                    app.state.poll_task.cancel()
                
                state.aircraft = sample
                state.error = None
                state.polled_at_unix_s = 123.0
                
                response = client.get("/api/aircraft")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["polled_at_unix_s"], 123.0)
                self.assertEqual(len(payload["aircraft"]), 1)
                self.assertEqual(payload["aircraft"][0]["hex"], "abc123")
                self.assertIn("system_position", payload)
                self.assertIsNotNone(payload["system_position"])
                self.assertAlmostEqual(payload["system_position"]["lat"], 49.121479)
                self.assertAlmostEqual(payload["system_position"]["lon"], 9.211960)

    def test_select_missing_returns_404(self) -> None:
        TestClient, create_app, _Aircraft = self._imports_or_skip()
        with mock.patch.dict(os.environ, {"GLOBE_MODE": "disabled"}, clear=False):
            app = create_app()

            with TestClient(app) as client:
                response = client.post("/api/select", json={"hex": "doesnotexist"})
                self.assertEqual(response.status_code, 404)

    def test_select_tracks_aircraft_and_unselect_clears_it(self) -> None:
        TestClient, create_app, Aircraft = self._imports_or_skip()
        from backend.app.models import AircraftMetadata, GlobeForwardResult

        with mock.patch.dict(os.environ, {"GLOBE_MODE": "disabled"}, clear=False):
            app = create_app()
            state = app.state.dump1090

            with TestClient(app) as client, mock.patch(
                "backend.app.main.forward_to_globe",
                new=mock.AsyncMock(return_value=GlobeForwardResult(sent=True, mode="mqtt", detail=None)),
            ), mock.patch(
                "backend.app.main.get_aircraft_metadata",
                new=mock.AsyncMock(
                    return_value=AircraftMetadata(
                        hex="abc123",
                        image_url=None,
                        type=None,
                        airline=None,
                        placeholder=True,
                        from_cache=False,
                    )
                )
            ):
                if app.state.poll_task:
                    app.state.poll_task.cancel()
                state.aircraft = [Aircraft(hex="abc123", flight="TEST123", lat=1.0, lon=2.0, altitude=1000, speed=250)]
                state.error = None

                response = client.post("/api/select", json={"hex": "abc123"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(state.selected_hex, "abc123")
                self.assertEqual(state.last_forwarded_signature, (1.0, 2.0, 1000.0, 250.0))

                response = client.post("/api/unselect")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"ok": True})
                self.assertIsNone(state.selected_hex)
                self.assertIsNone(state.last_forwarded_signature)

    def test_aircraft_signature_changes_when_position_updates(self) -> None:
        self._imports_or_skip()
        from backend.app.main import _aircraft_signature, _pick_selected_for_republish
        from backend.app.models import Aircraft
        from backend.app.state import Dump1090State

        a1 = Aircraft(hex="abc123", flight="TEST123", lat=1.0, lon=2.0, altitude=1000, speed=250)
        a2 = Aircraft(hex="abc123", flight="TEST123", lat=1.1, lon=2.0, altitude=1000, speed=250)

        self.assertNotEqual(_aircraft_signature(a1), _aircraft_signature(a2))

        state = Dump1090State(source_file_path="/tmp/aircraft.json", poll_interval_s=1.0)
        state.selected_hex = "abc123"
        state.last_forwarded_signature = _aircraft_signature(a1)

        self.assertEqual(_pick_selected_for_republish(state, [a1]), None)
        republish = _pick_selected_for_republish(state, [a2])
        self.assertIsNotNone(republish)
        assert republish is not None
        self.assertEqual(republish[0].hex, "abc123")
        self.assertEqual(republish[1], _aircraft_signature(a2))
