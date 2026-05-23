"""search_text tool: token-overlap ranking and locator passthrough."""
from app.agents.per_file._tools.search_text import search_text
from app.schemas import ParsedFile, ParsedSegment


def _pf() -> ParsedFile:
    """Return a three-line markdown ParsedFile for search ranking tests."""
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="Leads waiting > 24h before first response.",
                          locator={"type": "text", "line_start": 1, "line_end": 1}),
            ParsedSegment(text="CSR manually copies CRM notes.",
                          locator={"type": "text", "line_start": 2, "line_end": 2}),
            ParsedSegment(text="Producer follow-up inconsistent.",
                          locator={"type": "text", "line_start": 3, "line_end": 3}),
        ],
    )


def test_search_text_ranks_token_overlap_high():
    """Segments sharing more query tokens rank above ones with less overlap."""
    hits = search_text(_pf(), query="lead response time", top_k=2)
    assert len(hits) == 2
    assert hits[0]["text"].startswith("Leads waiting")


def test_search_text_returns_locator_with_each_hit():
    """Each hit dict carries the segment's locator unchanged."""
    hits = search_text(_pf(), query="csr copies notes", top_k=1)
    assert hits[0]["locator"]["line_start"] == 2


def test_search_text_caps_at_top_k():
    """The hits list is truncated to at most top_k entries."""
    hits = search_text(_pf(), query="the", top_k=2)
    assert len(hits) <= 2
