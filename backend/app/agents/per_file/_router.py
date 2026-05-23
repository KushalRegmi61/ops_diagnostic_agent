"""Typed tool dispatcher for the per-file ReAct loop.

Parses the LLM's ``{tool, args}`` reply into a ToolCall and routes it to the
matching function under ``_tools/``. Unknown tool names raise so the loop can
log the failure and continue rather than silently dropping the call.
"""
from typing import Any

from pydantic import BaseModel

from app.agents.per_file._state import WorkingState
from app.agents.per_file._tools.cite_locator import cite_locator
from app.agents.per_file._tools.extract_lead_row import extract_lead_row
from app.agents.per_file._tools.extract_pain_signal import extract_pain_signal
from app.agents.per_file._tools.extract_workflow import extract_workflow
from app.agents.per_file._tools.finalize_summary import finalize_summary
from app.agents.per_file._tools.read_segment import read_segment
from app.agents.per_file._tools.search_text import search_text
from app.schemas import ParsedFile


class ToolCall(BaseModel):
    """Parsed tool invocation from a single ReAct iteration."""
    tool: str
    args: dict


def dispatch(call: ToolCall, *, parsed: ParsedFile, ws: WorkingState) -> Any:
    """Route ``call`` to its tool implementation; raises ValueError on unknown tool names."""
    name = call.tool
    args = call.args

    if name == "search_text":
        return search_text(parsed, **args)
    if name == "read_segment":
        return read_segment(parsed, **args)
    if name == "extract_workflow":
        return extract_workflow(ws, **args)
    if name == "extract_pain_signal":
        return extract_pain_signal(ws, **args)
    if name == "extract_lead_row":
        return extract_lead_row(ws, **args)
    if name == "cite_locator":
        return cite_locator(parsed, **args)
    if name == "finalize_summary":
        return finalize_summary(ws, **args)
    raise ValueError(f"Unknown tool: {name}")
