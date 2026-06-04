"""JSON parser. Groups an arbitrary document's leaf values by their parent
RFC 6901 JSON Pointer, emitting one ParsedSegment per object (``key: value``
lines). The parent pointer is the locator, so excerpts round-trip via exact
parent-pointer match.
"""
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


def _group_by_parent(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Group (leaf_pointer, value) pairs by parent pointer into (parent, block) segments.

    Parent pointer = leaf pointer minus its last token. Block text joins each
    leaf's last-token key with its value as ``key: value`` lines, preserving
    first-seen parent order.
    """
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for ptr, val in pairs:
        parent, _, last = ptr.rpartition("/")
        if parent not in groups:
            groups[parent] = []
            order.append(parent)
        groups[parent].append(f"{last}: {val}")
    return [(parent, "\n".join(groups[parent])) for parent in order]


def parse(*, file_id: str, file_name: str, path: Path) -> ParsedFile:
    """Load the JSON at ``path`` and emit one ``json``-locator segment per parent object."""
    data = _json.loads(path.read_text())
    pairs = _flatten(data)
    segments = [
        ParsedSegment(text=block, locator={"type": "json", "pointer": parent})
        for parent, block in _group_by_parent(pairs)
    ]
    return ParsedFile(file_id=file_id, file_name=file_name, type="json", segments=segments)


def excerpt(parsed: ParsedFile, locator: dict) -> str:
    """Return the grouped object text whose parent JSON pointer matches ``locator['pointer']``."""
    ptr = locator["pointer"]
    for seg in parsed.segments:
        if seg.locator["pointer"] == ptr:
            return seg.text
    raise ValueError(f"Pointer {ptr} not found")
