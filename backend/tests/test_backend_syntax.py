"""
Syntax-level tests for the backend codebase.

These tests do not require third-party dependencies. They ensure that all Python files
in backend/app parse correctly, which catches obvious syntax errors early.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


class TestBackendSyntax(unittest.TestCase):
    def test_backend_app_files_parse(self) -> None:
        root = Path(__file__).resolve().parents[1] / "app"
        py_files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
        self.assertGreater(len(py_files), 0, "No backend/app python files found to test")

        for path in py_files:
            with self.subTest(file=str(path)):
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(path))

