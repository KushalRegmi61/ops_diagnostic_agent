"""Pydantic schema tests: locators, Source, ParsedFile, ExtractionError, FileRef.

Exercises the typed boundary contracts that the parsers and per-file agents
emit. Locator round-trip semantics (text reachable through ``parsers.excerpt``)
live in the parser-specific tests.
"""
import pytest
from pydantic import ValidationError

from app.schemas import (
    DocxLocator,
    ExtractionError,
    FileRef,
    JsonLocator,
    MboxLocator,
    ParsedFile,
    ParsedSegment,
    PdfLocator,
    Source,
    TableLocator,
    TextLocator,
    TranscriptLocator,
    XlsxLocator,
)


def test_pdf_locator_validates():
    """PdfLocator accepts page + span bounds and exposes its discriminator type."""
    loc = PdfLocator(page=2, span_start=10, span_end=40)
    assert loc.type == "pdf"
    assert loc.model_dump()["page"] == 2


def test_source_attaches_locator():
    """Source carries a typed locator coerced from a dict via the discriminator."""
    src = Source(
        file_id="f1",
        file_name="sop.pdf",
        type="pdf",
        locator={"type": "pdf", "page": 2, "span_start": 10, "span_end": 40},
    )
    assert src.locator.page == 2


def test_transcript_locator_requires_timestamps():
    """TranscriptLocator without ts_start/ts_end fails validation."""
    with pytest.raises(ValidationError):
        TranscriptLocator(line_start=1, line_end=2)  # missing ts_start, ts_end


def test_parsed_file_has_segments_with_locators():
    """ParsedFile holds ParsedSegment entries each with a locator."""
    pf = ParsedFile(
        file_id="f1",
        file_name="x.pdf",
        type="pdf",
        segments=[
            ParsedSegment(text="hello", locator={"type": "pdf", "page": 1, "span_start": 0, "span_end": 5}),
        ],
    )
    assert pf.segments[0].text == "hello"


def test_extraction_error_validates():
    """ExtractionError captures file_id, stage, and message."""
    err = ExtractionError(file_id="f1", stage="parse", message="bad pdf")
    assert err.stage == "parse"


def test_file_ref_validates():
    """FileRef requires id, name, mime, blob path, and parser status."""
    ref = FileRef(
        file_id="f1",
        file_name="sop.pdf",
        mime_type="application/pdf",
        blob_path="/blobs/f1/sop.pdf",
        parser_status="ok",
    )
    assert ref.parser_status == "ok"


def test_unused_locator_imports_exist():
    """All non-PDF/transcript locator classes are importable from app.schemas."""
    # Compile-time signal that all locator classes are exported.
    assert DocxLocator and JsonLocator and MboxLocator and TableLocator and TextLocator and XlsxLocator
