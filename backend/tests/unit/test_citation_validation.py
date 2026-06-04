"""Unit tests for the shared source-validation helper used by the extract_* tools."""
from app.agents.per_file._tools._citation import _EXCERPT_BY_TYPE, _validate_sources
from app.schemas import ParsedFile, ParsedSegment


def _txt_parsed() -> ParsedFile:
    """A one-line txt ParsedFile whose line 1 resolves via the markdown excerpt helper."""
    return ParsedFile(
        file_id="f1", file_name="a.txt", type="txt",
        segments=[ParsedSegment(text="manual follow-up needed",
                                locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


def _src(line: int) -> dict:
    """Build a txt source dict pointing at a single line."""
    return {"file_id": "f1", "file_name": "a.txt", "type": "txt",
            "locator": {"type": "text", "line_start": line, "line_end": line}}


def test_dispatch_table_covers_all_parser_types():
    """_EXCERPT_BY_TYPE maps every supported file type to a parser module."""
    assert set(_EXCERPT_BY_TYPE) == {
        "pdf", "docx", "md", "txt", "transcript_vtt", "transcript_srt",
        "csv", "xlsx", "mbox", "json",
    }


def test_all_valid_sources_kept():
    """Every source that round-trips to non-empty text is kept; none dropped."""
    kept, dropped = _validate_sources(_txt_parsed(), [_src(1)])
    assert kept == [_src(1)]
    assert dropped == []


def test_one_bad_one_good_filters_to_good():
    """A source that resolves to empty text is dropped; the valid one is kept."""
    kept, dropped = _validate_sources(_txt_parsed(), [_src(1), _src(99)])
    assert kept == [_src(1)]
    assert dropped == [_src(99)]


def test_all_bad_returns_empty_kept():
    """When no source round-trips, kept is empty and all are dropped."""
    kept, dropped = _validate_sources(_txt_parsed(), [_src(99)])
    assert kept == []
    assert dropped == [_src(99)]
