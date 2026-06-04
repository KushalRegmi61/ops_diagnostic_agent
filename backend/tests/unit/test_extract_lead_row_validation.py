"""Unit tests: extract_lead_row validates its single cited source."""
from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.extract_lead_row import extract_lead_row
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    """A one-row csv ParsedFile so row 0 resolves and row 9 does not."""
    return ParsedFile(
        file_id="f1", file_name="leads.csv", type="csv",
        segments=[ParsedSegment(text="name=Acme | owner=",
                                locator={"type": "table", "row_index": 0})],
    )


def _src(row: int) -> dict:
    """A table source dict at a single row."""
    return {"file_id": "f1", "file_name": "leads.csv", "type": "csv",
            "locator": {"type": "table", "row_index": row}}


def test_valid_source_saves_row():
    """A source that round-trips -> row saved, ok True."""
    ws = WorkingState(file_id="f1", file_name="leads.csv")
    out = extract_lead_row(ws, parsed=_parsed(), raw={"name": "Acme"},
                           normalized={"company": "Acme"}, source=_src(0))
    assert out["ok"] is True
    assert len(ws.lead_rows) == 1


def test_invalid_source_saves_nothing():
    """A source that does not round-trip -> nothing saved, ok False, with a hint."""
    ws = WorkingState(file_id="f1", file_name="leads.csv")
    out = extract_lead_row(ws, parsed=_parsed(), raw={"name": "Acme"},
                           normalized={"company": "Acme"}, source=_src(9))
    assert out["ok"] is False
    assert "hint" in out
    assert ws.lead_rows == []
