import json as _json
from pathlib import Path

from app.schemas import ParsedFile, ParsedSegment


def _flatten(obj, prefix: str = "") -> list[tuple[str, str]]:
    """Walk JSON, emit (pointer, leaf_text) pairs using RFC 6901 pointers."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).replace("~", "~0").replace("/", "~1")
            out.extend(_flatten(v, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_flatten(v, f"{prefix}/{i}"))
    else:
        out.append((prefix or "/", str(obj)))
    return out


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    data = _json.loads(path.read_text())
    pairs = _flatten(data)
    segments = [
        ParsedSegment(text=val, locator={"type": "json", "pointer": ptr})
        for ptr, val in pairs
    ]
    return ParsedFile(file_id=file_id, file_name=file_name, type="json", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    ptr = locator["pointer"]
    for seg in parsed.segments:
        if seg.locator["pointer"] == ptr:
            return seg.text
    raise ValueError(f"Pointer {ptr} not found")
