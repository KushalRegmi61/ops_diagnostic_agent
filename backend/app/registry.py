"""Single source of truth for {file_type → per-file agent} dispatch.

Parser dispatch (mime → ParsedFile) and excerpt dispatch (ParsedFile.type → text)
already live in ``app.parsers`` via ``_MIME_ROUTES`` and ``_EXCERPT_ROUTES``.
This module adds the third axis the graph needs: which per-file ReAct agent
runs against each ParsedFile.type.

Adding a new file type now requires coordinated edits in two files:
  app/parsers/__init__.py  — _MIME_ROUTES + _EXCERPT_ROUTES
  app/registry.py          — AGENT_BY_FILE_TYPE

The test in tests/unit/test_registry.py guarantees the three maps stay aligned.
"""
from __future__ import annotations

import importlib
from types import ModuleType


# ParsedFile.type -> app.agents.per_file module name.
AGENT_BY_FILE_TYPE: dict[str, str] = {
    "pdf": "pdf",
    "docx": "docx",
    "md": "markdown",
    "txt": "markdown",
    "transcript_vtt": "transcript",
    "transcript_srt": "transcript",
    "csv": "table",
    "xlsx": "table",
    "mbox": "mbox",
    "json": "json",
}


def get_agent_module(file_type: str) -> ModuleType | None:
    """Return the per-file agent module for ``file_type``, or None if unknown."""
    name = AGENT_BY_FILE_TYPE.get(file_type)
    if name is None:
        return None
    return importlib.import_module(f"app.agents.per_file.{name}")
