"""SubRip (.srt) transcript parser. One ParsedSegment per subtitle entry,
locator type ``transcript`` with the cue index and stringified timestamps.
"""
from pathlib import Path

import srt as srtlib

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    """Read a .srt file and emit one segment per subtitle, tagged ``transcript_srt``."""
    raw = path.read_text()
    segments: list[ParsedSegment] = []
    for idx, sub in enumerate(srtlib.parse(raw), start=1):
        segments.append(ParsedSegment(
            text=sub.content,
            locator={
                "type": "transcript",
                "line_start": idx,
                "line_end": idx,
                "ts_start": str(sub.start),
                "ts_end": str(sub.end),
            },
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="transcript_srt", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    """Return the subtitle text whose cue index equals ``locator['line_start']``."""
    line = locator["line_start"]
    for seg in parsed.segments:
        if seg.locator["line_start"] == line:
            return seg.text
    raise ValueError(f"Cue {line} not found")
