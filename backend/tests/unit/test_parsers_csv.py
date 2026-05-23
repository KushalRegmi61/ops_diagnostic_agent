from pathlib import Path

from app.parsers.csv import excerpt, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "leads.csv"


def test_parse_csv_emits_one_segment_per_row():
    pf = parse(file_id="f1", file_name="leads.csv", path=FIXTURE)
    assert pf.type == "csv"
    assert len(pf.segments) == 3
    loc = pf.segments[0].locator
    assert loc["type"] == "table"
    assert loc["row_index"] == 0
    assert "Acme" in pf.segments[0].text


def test_excerpt_returns_row_text():
    pf = parse(file_id="f1", file_name="leads.csv", path=FIXTURE)
    text = excerpt(pf, {"type": "table", "row_index": 2})
    assert "Gamma" in text
