from pathlib import Path

from app.parsers.xlsx import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "leads.xlsx"


def test_parse_xlsx_emits_one_segment_per_row_per_sheet():
    pf = parse(file_id="f1", file_name="leads.xlsx", path=FIXTURE)
    assert pf.type == "xlsx"
    assert len(pf.segments) == 2
    loc = pf.segments[0].locator
    assert loc["type"] == "xlsx"
    assert loc["sheet"] == "Leads"
    assert loc["row_index"] == 0


def test_excerpt_returns_row_text():
    pf = parse(file_id="f1", file_name="leads.xlsx", path=FIXTURE)
    text = excerpt(pf, {"type": "xlsx", "sheet": "Leads", "row_index": 1})
    assert "Beta" in text
