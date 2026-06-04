"""Unit test: built extract_* StructuredTools thread `parsed` and reject bad sources."""
from app.agents.per_file._router import build_tools
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    """A one-line txt ParsedFile so line 1 resolves and line 99 does not."""
    return ParsedFile(
        file_id="f1", file_name="a.txt", type="txt",
        segments=[ParsedSegment(text="intake step",
                                locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


def _src(line: int) -> dict:
    """A txt source dict at a single line."""
    return {"file_id": "f1", "file_name": "a.txt", "type": "txt",
            "locator": {"type": "text", "line_start": line, "line_end": line}}


def test_built_extract_workflow_rejects_invalid_source():
    """Invoking the bound extract_workflow with an unresolvable source saves nothing."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    tools = build_tools(_parsed(), ws, agent_mode=True)
    out = tools["extract_workflow"].invoke({
        "name": "Intake", "actors": ["CSR"], "systems": ["CRM"],
        "steps": ["a"], "manual_touchpoints": ["re-key"], "sources": [_src(99)],
    })
    assert out["ok"] is False
    assert ws.workflows == []


def test_built_extract_workflow_keeps_valid_source():
    """Invoking the bound extract_workflow with a resolvable source saves the record."""
    ws = WorkingState(file_id="f1", file_name="a.txt")
    tools = build_tools(_parsed(), ws, agent_mode=True)
    out = tools["extract_workflow"].invoke({
        "name": "Intake", "actors": ["CSR"], "systems": ["CRM"],
        "steps": ["a"], "manual_touchpoints": ["re-key"], "sources": [_src(1)],
    })
    assert out["ok"] is True
    assert len(ws.workflows) == 1
