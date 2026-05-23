"""Plain-text parser. Delegates to the line-based logic in ``app.parsers.md`` so
``.txt`` and ``.md`` share identical segment and excerpt semantics — only the
ParsedFile ``type`` tag differs.
"""
from pathlib import Path

from app.parsers.md import _parse_lines
from app.parsers.md import excerpt as _md_excerpt
from app.schemas import ParsedFile


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    """Parse a plain text file into a ParsedFile of type ``txt`` (one segment per line)."""
    return _parse_lines(path, file_id, file_name, "txt")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    """Resolve a ``text`` locator against a txt ParsedFile via the markdown excerpt helper."""
    return _md_excerpt(parsed, locator)
