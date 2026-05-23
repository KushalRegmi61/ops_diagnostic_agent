"""Markdown parser. One ParsedSegment per line with a ``text`` locator carrying
1-based ``line_start``/``line_end``. The same helper is reused by the plain-text
parser so both file families share excerpt semantics.
"""
from pathlib import Path

from app.schemas import ParsedFile, ParsedSegment


def _parse_lines(path: Path, file_id: str, file_name: str, file_type: str) -> ParsedFile:
    """Read ``path`` and emit one ParsedSegment per line, tagged with the given ``file_type``."""
    raw = path.read_text()
    lines = raw.splitlines()
    segments = [
        ParsedSegment(
            text=line,
            locator={"type": "text", "line_start": i + 1, "line_end": i + 1},
        )
        for i, line in enumerate(lines)
    ]
    return ParsedFile(file_id=file_id, file_name=file_name, type=file_type, segments=segments)


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    """Parse a markdown file into one line-per-segment ParsedFile of type ``md``."""
    return _parse_lines(path, file_id, file_name, "md")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    """Join the segment texts whose ``line_start`` falls within ``[line_start, line_end]``."""
    start = locator["line_start"]
    end = locator["line_end"]
    lines = [
        seg.text for seg in parsed.segments
        if start <= seg.locator["line_start"] <= end
    ]
    if not lines:
        raise ValueError(f"No lines in range [{start},{end}]")
    return "\n".join(lines)
