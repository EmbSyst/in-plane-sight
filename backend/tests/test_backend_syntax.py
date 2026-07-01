"""
Syntax-Level Tests für die Backend Codebase.

Diese Tests benötigen keine Drittanbieter-Abhängigkeiten. Sie stellen sicher, dass alle Python Dateien
in backend/app korrekt geparst werden können, was offensichtliche Syntaxfehler frühzeitig abfängt.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


class TestBackendSyntax(unittest.TestCase):
    def test_backend_app_files_parse(self) -> None:
        root = Path(__file__).resolve().parents[1] / "app"
        py_files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
        self.assertGreater(len(py_files), 0, "Keine Python-Dateien im backend/app Verzeichnis gefunden")

        for path in py_files:
            with self.subTest(file=str(path)):
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(path))

