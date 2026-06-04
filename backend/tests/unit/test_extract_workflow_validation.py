"""Unit tests: extract_workflow validates and filters its cited sources."""
from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.extract_workflow import extract_workflow
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    """A two-line txt ParsedFile so line 1 resolves and line 99 does not."""
    return ParsedFile(
        file_id="f1", file_name="a.txt", type="txt",
        segments=[
            ParsedSegment(text="intake step one", locator={"type": "text", "line_start": 1, "line_end": 1}),
            ParsedSegment(text="intake step two", locator={"type": "text", "line_start": 2, "line_end": 2}),
        ],
    )


def _src(line: int) -> dict:
    """A txt source dict at a single line."""
    return {"file_id": "f1", "file_name": "a.txt", "type": "txt",
            "locator": {"type": "text", "line_start": line, "line_end": line}}


def _kwargs(sources):
    """Common extract_workflow kwargs with the given sources."""
    return dict(name="Intake", actors=["CSR"], systems=["CRM"], steps=["a", "b"],
                manual_touchpoints=["re-key"], sources=sources)


def test_keeps_valid_sources_and_saves():
    """At least one valid source -> record saved with only kept sources, ok True."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    out = extract_workflow(ws, parsed=_parsed(), **_kwargs([_src(1), _src(99)]))
    assert out["ok"] is True
    assert out["dropped_sources"] == [_src(99)]
    assert len(ws.workflows) == 1
    assert [s.locator.line_start for s in ws.workflows[0].sources] == [1]


def test_all_invalid_saves_nothing():
    """Every source invalid -> nothing saved, ok False, with a hint."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    out = extract_workflow(ws, parsed=_parsed(), **_kwargs([_src(99)]))
    assert out["ok"] is False
    assert out["dropped_sources"] == [_src(99)]
    assert "hint" in out
    assert ws.workflows == []
