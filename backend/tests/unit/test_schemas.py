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
    loc = PdfLocator(page=2, span_start=10, span_end=40)
    assert loc.type == "pdf"
    assert loc.model_dump()["page"] == 2


def test_source_attaches_locator():
    src = Source(
        file_id="f1",
        file_name="sop.pdf",
        type="pdf",
        locator={"type": "pdf", "page": 2, "span_start": 10, "span_end": 40},
    )
    assert src.locator["page"] == 2


def test_transcript_locator_requires_timestamps():
    with pytest.raises(ValidationError):
        TranscriptLocator(line_start=1, line_end=2)  # missing ts_start, ts_end


def test_parsed_file_has_segments_with_locators():
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
    err = ExtractionError(file_id="f1", stage="parse", message="bad pdf")
    assert err.stage == "parse"


def test_file_ref_validates():
    ref = FileRef(
        file_id="f1",
        file_name="sop.pdf",
        mime_type="application/pdf",
        blob_path="/blobs/f1/sop.pdf",
        parser_status="ok",
    )
    assert ref.parser_status == "ok"


def test_unused_locator_imports_exist():
    # Compile-time signal that all locator classes are exported.
    assert DocxLocator and JsonLocator and MboxLocator and TableLocator and TextLocator and XlsxLocator
