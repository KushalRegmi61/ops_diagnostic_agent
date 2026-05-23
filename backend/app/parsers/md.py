from pathlib import Path

from app.schemas import ParsedFile, ParsedSegment


def _parse_lines(path: Path, file_id: str, file_name: str, file_type: str) -> ParsedFile:
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
    return _parse_lines(path, file_id, file_name, "md")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    start = locator["line_start"]
    end = locator["line_end"]
    lines = [
        seg.text for seg in parsed.segments
        if start <= seg.locator["line_start"] <= end
    ]
    if not lines:
        raise ValueError(f"No lines in range [{start},{end}]")
    return "\n".join(lines)
