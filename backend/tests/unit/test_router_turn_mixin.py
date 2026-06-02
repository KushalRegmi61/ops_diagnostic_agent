"""Every tool's args carry AgentTurn fields; they are stripped before dispatch."""
from app.agents.per_file._router import build_tools, TURN_FIELDS
from app.agents.per_file._state import WorkingState
from app.schemas import ParsedFile, ParsedSegment


def _parsed() -> ParsedFile:
    return ParsedFile(
        file_id="f1", file_name="n.md", type="md",
        segments=[ParsedSegment(text="Leads wait > 24h.", locator={"type": "text", "line_start": 1, "line_end": 1})],
    )


def test_every_tool_schema_includes_turn_fields():
    tools = build_tools(_parsed(), WorkingState(file_id="f1", file_name="n.md"))
    for name, tool in tools.items():
        fields = tool.args_schema.model_fields
        for tf in TURN_FIELDS:
            assert tf in fields, f"{name} missing {tf}"


def test_tool_runs_when_turn_fields_present_and_are_stripped():
    tools = build_tools(_parsed(), WorkingState(file_id="f1", file_name="n.md"))
    result = tools["search_text"].invoke(
        {"query": "leads", "top_k": 1, "open_gap": "x", "plan_next": "y", "ready_to_finalize": False}
    )
    assert isinstance(result, list)
    assert result and result[0]["segment_index"] == 0
