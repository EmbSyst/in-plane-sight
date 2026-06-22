"""
Tests for the globe forwarding module.

The forwarding layer is designed to be modular, so these tests focus on the
configuration gatekeeping behavior that should be stable across transports.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock


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
        os.environ["GLOBE_MODE"] = "mqtt"
        forward_to_globe = self._forward_to_globe_or_skip()

        aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=None, lon=None, altitude=None, speed=None)
        result = await forward_to_globe(aircraft)
        self.assertFalse(result.sent)
        self.assertEqual(result.mode, "mqtt")
        self.assertIn("lat/lon", (result.detail or "").lower())

    async def test_unknown_mode_is_rejected(self) -> None:
        os.environ["GLOBE_MODE"] = "something-else"
        forward_to_globe = self._forward_to_globe_or_skip()

        aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)
        result = await forward_to_globe(aircraft)
        self.assertFalse(result.sent)
        self.assertEqual(result.mode, "something-else")
        self.assertIn("unknown", (result.detail or "").lower())

    async def test_mqtt_mode_publishes_two_messages(self) -> None:
        class _FakeClient:
            def __init__(self):
                self.publish_calls = []

            def connect(self, _host, _port, _keepalive):
                return 0

            def loop_start(self):
                return None

            def publish(self, topic, payload, qos, retain):
                self.publish_calls.append((topic, payload, qos, retain))
                return SimpleNamespace(rc=0)

        os.environ["GLOBE_MODE"] = "mqtt"
        os.environ["GLOBE_MQTT_HOST"] = "test.mosquitto.org"
        os.environ["GLOBE_MQTT_PORT"] = "1883"
        os.environ["GLOBE_MQTT_TOPIC"] = "in-plane-sight"
        os.environ["GLOBE_MQTT_QOS"] = "0"
        os.environ["GLOBE_MQTT_RETAIN"] = "0"
        os.environ["GLOBE_DUMMY_X"] = "0"
        os.environ["GLOBE_DUMMY_Y"] = "0"

        forward_to_globe = self._forward_to_globe_or_skip()
        from backend.app.services import globe as globe_module

        fake = _FakeClient()
        with mock.patch.object(globe_module.mqtt, "Client", return_value=fake):
            aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)
            result = await forward_to_globe(aircraft)

        self.assertTrue(result.sent)
        self.assertEqual(result.mode, "mqtt")
        self.assertEqual(len(fake.publish_calls), 2)
        self.assertEqual(fake.publish_calls[0][0], "in-plane-sight")
        self.assertEqual(fake.publish_calls[0][2:], (0, False))
        self.assertIn('"type":"change_display_mode"', fake.publish_calls[0][1])
        self.assertIn('"type":"change_plane_position"', fake.publish_calls[1][1])
