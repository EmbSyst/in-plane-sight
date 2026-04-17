"""
Tests for Planespotters integration.

These tests mock outbound HTTP calls to avoid network dependency and validate caching,
parsing and fallback behavior.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch


class TestPlanespotters(unittest.IsolatedAsyncioTestCase):
    async def test_caches_by_hex_and_parses_fields(self) -> None:
        from backend.app.services import planespotters

        payload = {
            "photos": [
                {
                    "photographer": "Jane Doe",
                    "aircraft": {"type": "Airbus A320-214"},
                    "airline": {"name": "Example Air"},
                    "thumbnail_large": {"src": "https://example.invalid/photo.jpg"},
                }
            ]
        }

        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return payload

        async def _fake_get(_url: str):
            return _Resp()

        with patch("backend.app.services.planespotters.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(side_effect=_fake_get)

            planespotters._CACHE.clear()
            meta1 = await planespotters.get_aircraft_metadata("4d22b4")
            meta2 = await planespotters.get_aircraft_metadata("4d22b4")

            self.assertEqual(meta1.hex, "4d22b4")
            self.assertEqual(meta1.type, "Airbus A320-214")
            self.assertEqual(meta1.airline, "Example Air")
            self.assertEqual(meta1.photographer, "Jane Doe")
            self.assertEqual(meta1.image_url, "https://example.invalid/photo.jpg")
            self.assertFalse(meta1.placeholder)

            self.assertTrue(meta2.from_cache)
            self.assertEqual(instance.get.await_count, 1)

    async def test_fallback_to_placeholder_on_404(self) -> None:
        from backend.app.services import planespotters

        class _Resp404:
            status_code = 404

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return json.loads("{}")

        async def _fake_get(_url: str):
            return _Resp404()

        with patch("backend.app.services.planespotters.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(side_effect=_fake_get)

            planespotters._CACHE.clear()
            meta = await planespotters.get_aircraft_metadata("abc123")
            self.assertTrue(meta.placeholder)
            self.assertTrue(meta.image_url and meta.image_url.endswith("aircraft-placeholder.svg"))

