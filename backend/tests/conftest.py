"""Shared pytest configuration.

Prepends the backend project root to ``sys.path`` so test modules can import
the ``app`` package without an editable install being present in the active
interpreter.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
