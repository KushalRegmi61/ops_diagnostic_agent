"""Tool for reading one exact parsed segment by index.

The ReAct loop shows the LLM short previews of parsed segments and lets it use
``search_text`` to find candidates. Once the model decides a segment is worth
inspecting, it calls ``read_segment`` with the segment's zero-based index.

This tool returns the full segment text plus the segment locator. The text is
what the model should reason over; the locator is what it later validates with
``cite_locator`` and attaches to extracted workflows, pain signals, or lead
rows as evidence.

``read_segment`` does not summarize, search, or mutate state. It is a precise
file-reading operation over the parser's normalized ``ParsedFile.segments``.
"""
from app.schemas import ParsedFile


def read_segment(parsed: ParsedFile, *, segment_index: int) -> dict:
    """Return ``{text, locator}`` for one segment; raise if the index is invalid."""
    if segment_index < 0 or segment_index >= len(parsed.segments):
        raise ValueError(f"segment_index {segment_index} out of range")
    seg = parsed.segments[segment_index]
    return {"text": seg.text, "locator": seg.locator}
