"""Per-file ReAct tool router dispatch behavior."""
import pytest
from pydantic import ValidationError

from app.agents.per_file._router import ToolCall, dispatch
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment


def _pf() -> ParsedFile:
    """Return a one-segment markdown ParsedFile for router exercises."""
    return ParsedFile(
        file_id="f1", file_name="x.md", type="md",
        segments=[
            ParsedSegment(text="step", locator={"type": "text", "line_start": 1, "line_end": 1}),
        ],
    )


def test_dispatch_search_text():
    """dispatch routes 'search_text' to the search tool and returns hits."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="search_text", args={"query": "step", "top_k": 1})
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert isinstance(result, list)


def test_dispatch_finalize_summary_returns_file_summary():
    """dispatch routes 'finalize_summary' and returns a FileSummary."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="finalize_summary", args={"one_paragraph_summary": "done"})
    fs = dispatch(call, parsed=_pf(), ws=ws)
    assert fs.one_paragraph_summary == "done"


def test_dispatch_unknown_tool_raises():
    """Unknown tool names fail ToolCall validation before dispatch."""
    with pytest.raises(ValidationError, match="literal_error"):
        ToolCall(tool="nope", args={})


def test_dispatch_invalid_args_raises():
    """Invalid tool arguments are surfaced as exceptions, never swallowed."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="read_segment", args={"wrong_arg": 1})
    with pytest.raises(Exception):
        dispatch(call, parsed=_pf(), ws=ws)


def test_dispatch_read_segment_defaults_to_first_segment_when_args_empty():
    """An empty read_segment args object falls back to the first visible segment."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(tool="read_segment", args={})
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert result["text"] == "step"


def test_dispatch_read_segment_accepts_locator_arg():
    """Locator-shaped read_segment calls are resolved back to a segment index."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(
        tool="read_segment",
        args={"locator": {"type": "text", "line_start": 1, "line_end": 1}},
    )
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert result["text"] == "step"


def test_dispatch_read_segment_accepts_flat_locator_args():
    """Flat locator keys from the LLM can identify the segment to read."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(
        tool="read_segment",
        args={"type": "text", "line_start": 1, "line_end": 1},
    )
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert result["text"] == "step"


def test_dispatch_ignores_extra_locator_args():
    """Extra locator-shaped keys from the LLM do not break otherwise valid tool calls."""
    ws = WorkingState(file_id="f1", file_name="x.md")
    call = ToolCall(
        tool="read_segment",
        args={"segment_index": 0, "type": "xlsx", "sheet": "Pipeline"},
    )
    result = dispatch(call, parsed=_pf(), ws=ws)
    assert result["text"] == "step"
