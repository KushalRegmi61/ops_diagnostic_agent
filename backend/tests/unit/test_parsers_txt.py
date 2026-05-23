"""Plain-text parser: per-line segmentation and line-range excerpts."""
from pathlib import Path

from app.parsers.txt import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "notes.txt"


def test_parse_txt_emits_lines():
    """parse() emits one segment per line with text-typed locators."""
    pf = parse(file_id="f1", file_name="notes.txt", path=FIXTURE)
    assert pf.type == "txt"
    assert len(pf.segments) == 3
    assert pf.segments[0].locator == {"type": "text", "line_start": 1, "line_end": 1}


def test_excerpt_returns_line_range():
    """excerpt() returns the joined lines for the locator's line range."""
    pf = parse(file_id="f1", file_name="notes.txt", path=FIXTURE)
    text = excerpt(pf, {"type": "text", "line_start": 2, "line_end": 3})
    assert "document collection" in text
