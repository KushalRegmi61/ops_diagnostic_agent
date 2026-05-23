from pathlib import Path

from app.parsers.md import _parse_lines
from app.parsers.md import excerpt as _md_excerpt
from app.schemas import ParsedFile


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    return _parse_lines(path, file_id, file_name, "txt")


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    return _md_excerpt(parsed, locator)
