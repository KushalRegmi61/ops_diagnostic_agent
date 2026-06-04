"""Unit tests: extract_pain_signal validates and filters its cited sources."""
from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.extract_pain_signal import extract_pain_signal
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    """A one-line txt ParsedFile so line 1 resolves and line 99 does not."""
    return ParsedFile(
        file_id="f1", file_name="a.txt", type="txt",
        segments=[ParsedSegment(text="follow-up is stale",
                                locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


def _src(line: int) -> dict:
    """A txt source dict at a single line."""
    return {"file_id": "f1", "file_name": "a.txt", "type": "txt",
            "locator": {"type": "text", "line_start": line, "line_end": line}}


def test_keeps_valid_sources_and_saves():
    """At least one valid source -> signal saved with kept sources, ok True."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    out = extract_pain_signal(ws, parsed=_parsed(), text="stale follow-up",
                              category="delay", sources=[_src(1), _src(99)])
    assert out["ok"] is True
    assert out["dropped_sources"] == [_src(99)]
    assert len(ws.pain_signals) == 1
    assert [s.locator.line_start for s in ws.pain_signals[0].sources] == [1]


def test_all_invalid_saves_nothing():
    """Every source invalid -> nothing saved, ok False, with a hint."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    out = extract_pain_signal(ws, parsed=_parsed(), text="stale follow-up",
                              category="delay", sources=[_src(99)])
    assert out["ok"] is False
    assert "hint" in out
    assert ws.pain_signals == []
