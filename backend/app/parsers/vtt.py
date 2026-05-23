from pathlib import Path

import webvtt

from app.schemas import ParsedFile, ParsedSegment


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    segments: list[ParsedSegment] = []
    for idx, caption in enumerate(webvtt.read(str(path)), start=1):
        segments.append(ParsedSegment(
            text=caption.text,
            locator={
                "type": "transcript",
                "line_start": idx,
                "line_end": idx,
                "ts_start": caption.start,
                "ts_end": caption.end,
            },
        ))
    return ParsedFile(file_id=file_id, file_name=file_name, type="transcript_vtt", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    line = locator["line_start"]
    for seg in parsed.segments:
        if seg.locator["line_start"] == line:
            return seg.text
    raise ValueError(f"Cue {line} not found")
