"""
Tests for the globe forwarding module.

The forwarding layer is designed to be modular, so these tests focus on the
configuration gatekeeping behavior that should be stable across transports.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace


class TestGlobeForwarding(unittest.IsolatedAsyncioTestCase):
    def _forward_to_globe_or_skip(self):
        try:
            from backend.app.services.globe import forward_to_globe
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"globe module dependencies not available: {exc}")
        return forward_to_globe

    def setUp(self) -> None:
        self._old_env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)

    async def test_disabled_mode_does_not_send(self) -> None:
        os.environ["GLOBE_MODE"] = "disabled"
        forward_to_globe = self._forward_to_globe_or_skip()

        aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)
        result = await forward_to_globe(aircraft)
        self.assertFalse(result.sent)
        self.assertEqual(result.mode, "disabled")

    async def test_missing_position_is_rejected(self) -> None:
        os.environ["GLOBE_MODE"] = "udp"
        forward_to_globe = self._forward_to_globe_or_skip()

        aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=None, lon=None, altitude=None, speed=None)
        result = await forward_to_globe(aircraft)
        self.assertFalse(result.sent)
        self.assertEqual(result.mode, "udp")
        self.assertIn("lat/lon", (result.detail or "").lower())

    async def test_unknown_mode_is_rejected(self) -> None:
        os.environ["GLOBE_MODE"] = "something-else"
        forward_to_globe = self._forward_to_globe_or_skip()

        aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)
        result = await forward_to_globe(aircraft)
        self.assertFalse(result.sent)
        self.assertEqual(result.mode, "something-else")
        self.assertIn("unknown", (result.detail or "").lower())
