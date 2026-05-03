"""
API-level tests for the FastAPI application.

These tests are optional at runtime: if FastAPI/Starlette are not installed in the
current environment, the tests are skipped instead of failing.
"""

from __future__ import annotations

import os
import unittest


class TestApiEndpoints(unittest.TestCase):
    def _imports_or_skip(self):
        try:
            from starlette.testclient import TestClient  # type: ignore
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"starlette TestClient not available: {exc}")

        try:
            from backend.app.main import create_app
            from backend.app.models import Aircraft
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"backend app dependencies not available: {exc}")

        return TestClient, create_app, Aircraft

    def test_health(self) -> None:
        TestClient, create_app, _Aircraft = self._imports_or_skip()
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

    def test_aircraft_list_reflects_cache(self) -> None:
        TestClient, create_app, Aircraft = self._imports_or_skip()
        app = create_app()

        sample = [Aircraft(hex="abc123", flight="TEST123", lat=1.0, lon=2.0, altitude=1000, speed=250)]
        state = app.state.dump1090
        
        # When TestClient(app) is created, it fires the 'startup' event, which starts the background poller.
        # We need to set the state *after* the client has started, or cancel the task so it doesn't overwrite it.
        # Alternatively, we just mock the fetcher or override the state properties inside the block.
        
        with TestClient(app) as client, unittest.mock.patch.dict(
            os.environ,
            {"SYSTEM_LAT": "49.121479", "SYSTEM_LON": "9.211960"},
            clear=False,
        ):
            # Cancel the background poller so it doesn't overwrite our mock data
            # with connection errors (since dump1090 isn't actually running)
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
        app = create_app()

        with TestClient(app) as client:
            response = client.post("/api/select", json={"hex": "doesnotexist"})
            self.assertEqual(response.status_code, 404)
