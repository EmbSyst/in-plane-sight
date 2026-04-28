"""
Tests for resolving the system's own position (lat/lon).

These tests use only the Python standard library and do not require FastAPI.
"""

from __future__ import annotations

import os
import unittest


class TestSystemPosition(unittest.TestCase):
    def test_reads_lat_lon_from_env(self) -> None:
        from backend.app.services import system_position

        system_position.clear_system_position_cache()
        with unittest.mock.patch.dict(
            os.environ,
            {"SYSTEM_LAT": "49.121479", "SYSTEM_LON": "9.211960"},
            clear=False,
        ):
            pos = system_position.get_system_position()
            self.assertIsNotNone(pos)
            self.assertAlmostEqual(pos["lat"], 49.121479)
            self.assertAlmostEqual(pos["lon"], 9.211960)
            self.assertEqual(pos["source"], "env")

    def test_returns_none_when_env_missing(self) -> None:
        from backend.app.services import system_position

        system_position.clear_system_position_cache()
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            pos = system_position.get_system_position()
            self.assertIsNone(pos)
