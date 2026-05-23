from pathlib import Path

from app.parsers.docx import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sop.docx"


def test_parse_docx_emits_segments_per_paragraph():
    pf = parse(file_id="f1", file_name="sop.docx", path=FIXTURE)
    assert pf.type == "docx"
    assert len(pf.segments) == 3
    assert pf.segments[0].text == "Onboarding SOP"
    assert pf.segments[0].locator["paragraph_index"] == 0


def test_excerpt_returns_paragraph_slice():
    pf = parse(file_id="f1", file_name="sop.docx", path=FIXTURE)
    seg = pf.segments[1]
    text = excerpt(pf, {
        "type": "docx",
        "paragraph_index": 1,
        "span_start": 0,
        "span_end": len(seg.text),
    })
    assert text.startswith("Step 1")
