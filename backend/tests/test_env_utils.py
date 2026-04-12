"""
Tests for environment variable helpers.

These utilities are used across the backend to keep configuration parsing consistent.
"""

from __future__ import annotations

import os
import unittest

from backend.app.utils import get_env, get_env_float, get_env_int


class TestEnvUtils(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)

    def test_get_env_default_when_missing(self) -> None:
        os.environ.pop("X_TEST_MISSING", None)
        self.assertEqual(get_env("X_TEST_MISSING", "fallback"), "fallback")

    def test_get_env_default_when_blank(self) -> None:
        os.environ["X_TEST_BLANK"] = "   "
        self.assertEqual(get_env("X_TEST_BLANK", "fallback"), "fallback")

    def test_get_env_returns_stripped_value(self) -> None:
        os.environ["X_TEST_VALUE"] = "  hello  "
        self.assertEqual(get_env("X_TEST_VALUE", "fallback"), "hello")

    def test_get_env_float_parses_valid(self) -> None:
        os.environ["X_TEST_FLOAT"] = "1.25"
        self.assertAlmostEqual(get_env_float("X_TEST_FLOAT", 0.5), 1.25)

    def test_get_env_float_falls_back_on_invalid(self) -> None:
        os.environ["X_TEST_FLOAT_BAD"] = "nope"
        self.assertAlmostEqual(get_env_float("X_TEST_FLOAT_BAD", 0.5), 0.5)

    def test_get_env_int_parses_valid(self) -> None:
        os.environ["X_TEST_INT"] = "42"
        self.assertEqual(get_env_int("X_TEST_INT", 7), 42)

    def test_get_env_int_falls_back_on_invalid(self) -> None:
        os.environ["X_TEST_INT_BAD"] = "4.2"
        self.assertEqual(get_env_int("X_TEST_INT_BAD", 7), 7)
