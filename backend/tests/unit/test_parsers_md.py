"""Markdown parser: per-line segmentation and line-range excerpts."""
from pathlib import Path

from app.parsers.md import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "notes.md"


def test_parse_md_emits_one_segment_per_line():
    """parse() emits one segment per line with text-typed locators."""
    pf = parse(file_id="f1", file_name="notes.md", path=FIXTURE)
    assert pf.type == "md"
    assert pf.segments[0].locator["line_start"] == 1
    assert "Producer Notes" in pf.segments[0].text


def test_excerpt_returns_lines_in_range():
    """excerpt() returns the joined lines for a text line_start/line_end locator."""
    pf = parse(file_id="f1", file_name="notes.md", path=FIXTURE)
    text = excerpt(pf, {"type": "text", "line_start": 3, "line_end": 3})
    assert "Leads waiting" in text
