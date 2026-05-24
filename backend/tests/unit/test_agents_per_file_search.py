"""search_text tool: BM25 ranking, adapter metadata, and locator passthrough."""
from app.agents.per_file._tools.search_text import _documents_from_parsed, search_text
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


def test_documents_from_parsed_preserves_segment_metadata():
    """The LangChain Document adapter carries original segment identity."""
    docs = _documents_from_parsed(_pf())
    assert docs[1].page_content == "CSR manually copies CRM notes."
    assert docs[1].metadata["segment_index"] == 1
    assert docs[1].metadata["locator"] == {"type": "text", "line_start": 2, "line_end": 2}
    assert docs[1].metadata["file_id"] == "f1"
    assert docs[1].metadata["file_name"] == "x.md"
    assert docs[1].metadata["file_type"] == "md"


def test_search_text_empty_query_returns_original_order_with_zero_scores():
    """Tokenless queries avoid BM25 and return stable original-order hits."""
    hits = search_text(_pf(), query="   !!!   ", top_k=2)
    assert [h["segment_index"] for h in hits] == [0, 1]
    assert [h["score"] for h in hits] == [0.0, 0.0]


def test_search_text_empty_segments_returns_empty_list():
    """An empty ParsedFile has no searchable hits."""
    parsed = ParsedFile(file_id="f1", file_name="empty.md", type="md", segments=[])
    assert search_text(parsed, query="anything", top_k=3) == []


def test_search_text_top_k_zero_returns_empty_list():
    """Non-positive top_k means no hits."""
    assert search_text(_pf(), query="lead", top_k=0) == []


def test_search_text_bm25_favors_specific_terms():
    """Specific rare terms should beat generic operational overlap."""
    parsed = ParsedFile(
        file_id="f2",
        file_name="ops.md",
        type="md",
        segments=[
            ParsedSegment(
                text="Lead response time is discussed in generic weekly operations notes.",
                locator={"type": "text", "line_start": 1, "line_end": 1},
            ),
            ParsedSegment(
                text="BOR endorsement validation is stalled in the carrier portal.",
                locator={"type": "text", "line_start": 2, "line_end": 2},
            ),
        ],
    )
    hits = search_text(parsed, query="BOR endorsement validation", top_k=1)
    assert hits[0]["segment_index"] == 1
    assert hits[0]["text"].startswith("BOR endorsement")
