from pathlib import Path

import pytest

from app.parsers.pdf import excerpt, parse
from app.schemas import PdfLocator

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sop.pdf"


def test_parse_pdf_emits_segments_per_page():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    assert pf.type == "pdf"
    assert len(pf.segments) >= 2
    assert pf.segments[0].locator["page"] == 1
    assert pf.segments[1].locator["page"] == 2
    assert "Inbound Lead SOP" in pf.segments[0].text


def test_excerpt_returns_text_at_locator():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    seg = pf.segments[0]
    loc = PdfLocator(page=1, span_start=0, span_end=len(seg.text))
    text = excerpt(pf, loc.model_dump())
    assert text.startswith("Inbound Lead SOP")


def test_excerpt_invalid_page_raises():
    pf = parse(file_id="f1", file_name="sop.pdf", path=FIXTURE)
    with pytest.raises(ValueError):
        excerpt(pf, {"type": "pdf", "page": 999, "span_start": 0, "span_end": 5})
