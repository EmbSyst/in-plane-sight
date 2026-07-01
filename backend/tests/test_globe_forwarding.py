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

    def _globe_module_or_skip(self):
        try:
            from backend.app.services import globe
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"globe module dependencies not available: {exc}")
        return globe

    def setUp(self) -> None:
        self._old_env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)
        try:
            from backend.app.services import globe

            globe.shutdown_globe_transport()
        except Exception:
            pass

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

    async def test_mqtt_mode_publishes_selection_messages(self) -> None:
        from unittest.mock import patch

        globe = self._globe_module_or_skip()

        class _FakeClient:
            def __init__(self):
                self.published = []
                self.connected_to = None
                self.loop_started = False
                self.disconnected = False

            def connect_async(self, host, port, keepalive):
                self.connected_to = (host, port, keepalive)
                return 0

            def loop_start(self):
                self.loop_started = True

            def publish(self, topic, payload, qos, retain):
                self.published.append((topic, payload, qos, retain))
                return SimpleNamespace(rc=0)

            def loop_stop(self):
                self.loop_started = False

            def disconnect(self):
                self.disconnected = True

        fake_client = _FakeClient()
        os.environ["GLOBE_MODE"] = "mqtt"
        os.environ["GLOBE_MQTT_HOST"] = "test.mosquitto.org"
        os.environ["GLOBE_MQTT_PORT"] = "1883"
        os.environ["GLOBE_MQTT_TOPIC"] = "in-plane-sight"

        with patch("backend.app.services.globe.mqtt.Client", return_value=fake_client):
            globe.shutdown_globe_transport()
            aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)
            result = await globe.forward_to_globe(aircraft)

        self.assertTrue(result.sent)
        self.assertEqual(result.mode, "mqtt")
        self.assertEqual(fake_client.connected_to, ("test.mosquitto.org", 1883, 60))
        import json

        # Sollte zwei Nachrichten gesendet haben (change_display_mode und set_points)
        self.assertEqual(len(fake_client.published), 2)

        # Erste Nachricht: change_display_mode (mode=2)
        mode_payload = json.loads(fake_client.published[0][1])
        self.assertEqual(mode_payload["type"], "change_display_mode")
        self.assertEqual(mode_payload["mode"], 2)
        
        # Zweite Nachricht: set_points
        self.assertEqual(fake_client.published[1][0], "in-plane-sight")
        self.assertEqual(fake_client.published[1][2:], (0, False))
        points_payload = json.loads(fake_client.published[1][1])
        self.assertEqual(points_payload["type"], "set_points")
        self.assertEqual(len(points_payload["points"]), 1)
        self.assertEqual(points_payload["points"][0]["id"], "TEST")
        self.assertEqual(points_payload["points"][0]["lat"], 1.0)
        self.assertEqual(points_payload["points"][0]["lon"], 2.0)

    async def test_mqtt_mode_reuses_persistent_client(self) -> None:
        from unittest.mock import patch

        globe = self._globe_module_or_skip()

        class _FakeClient:
            def __init__(self):
                self.connect_calls = 0
                self.publish_calls = 0

            def connect_async(self, host, port, keepalive):
                self.connect_calls += 1
                return 0

            def loop_start(self):
                return None

            def publish(self, topic, payload, qos, retain):
                self.publish_calls += 1
                return SimpleNamespace(rc=0)

            def loop_stop(self):
                return None

            def disconnect(self):
                return None

        fake_client = _FakeClient()
        os.environ["GLOBE_MODE"] = "mqtt"

        with patch("backend.app.services.globe.mqtt.Client", return_value=fake_client):
            globe.shutdown_globe_transport()
            aircraft = SimpleNamespace(hex="abc123", flight="TEST", lat=1.0, lon=2.0, altitude=None, speed=None)

            # Erste Flugzeug-Auswahl -> sendet 2 Nachrichten (Mode + Points)
            await globe.forward_to_globe(aircraft)
            self.assertEqual(fake_client.connect_calls, 1)
            self.assertEqual(fake_client.publish_calls, 2)

            # Zweite Flugzeug-Auswahl -> sendet wieder 2 Nachrichten (Mode + Points) -> gesamt 4
            await globe.forward_to_globe(aircraft)
            self.assertEqual(fake_client.connect_calls, 1)  # Kein neuer Verbindungsaufbau!
            self.assertEqual(fake_client.publish_calls, 4)

    async def test_change_pwm_publishes_motor_messages(self) -> None:
        from unittest.mock import patch

        globe = self._globe_module_or_skip()

        class _FakeClient:
            def __init__(self):
                self.published = []

            def connect_async(self, host, port, keepalive):
                return 0

            def loop_start(self):
                return None

            def publish(self, topic, payload, qos, retain):
                self.published.append(payload)
                return SimpleNamespace(rc=0)

            def loop_stop(self):
                return None

            def disconnect(self):
                return None

        fake_client = _FakeClient()
        os.environ["GLOBE_MODE"] = "mqtt"

        with patch("backend.app.services.globe.mqtt.Client", return_value=fake_client):
            globe.shutdown_globe_transport()
            result_off = await globe.publish_change_pwm(0)
            result_run = await globe.publish_change_pwm(1, 400)

        self.assertTrue(result_off.sent)
        self.assertTrue(result_run.sent)
        self.assertIn('"type":"change_PWM"', fake_client.published[0])
        self.assertIn('"mode":0', fake_client.published[0])
        self.assertIn('"rpm":[]', fake_client.published[0])
        self.assertIn('"mode":1', fake_client.published[1])
        self.assertIn('"rpm":[400]', fake_client.published[1])
