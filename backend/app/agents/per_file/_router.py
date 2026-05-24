"""Typed tool dispatcher for the per-file ReAct loop.

Parses the LLM's ``{tool, args}`` reply into a ToolCall and routes it to the
matching function under ``_tools/``. Unknown tool names raise so the loop can
log the failure and continue rather than silently dropping the call.
"""
from typing import Any, Literal

from langchain_core.tools import StructuredTool
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


ToolName = Literal[
    "search_text",
    "read_segment",
    "extract_workflow",
    "extract_pain_signal",
    "extract_lead_row",
    "cite_locator",
    "finalize_summary",
]


class ToolCall(BaseModel):
    """Parsed tool invocation from a single ReAct iteration."""
    tool: ToolName
    args: dict


class SearchTextArgs(BaseModel):
    """Arguments for searching over parsed file segments."""
    query: str
    top_k: int = 3


class ReadSegmentArgs(BaseModel):
    """Arguments for reading one parsed segment by its zero-based index."""
    segment_index: int


class ExtractWorkflowArgs(BaseModel):
    """Arguments for recording a workflow found in the file."""
    name: str
    actors: list[str]
    systems: list[str]
    steps: list[str]
    manual_touchpoints: list[str]
    sources: list[dict]


class ExtractPainSignalArgs(BaseModel):
    """Arguments for recording a pain signal found in the file."""
    text: str
    category: Literal["delay", "error", "repetition", "handoff", "missing_data", "visibility_gap", "revenue_leak"]
    sources: list[dict]


class ExtractLeadRowArgs(BaseModel):
    """Arguments for recording a structured lead row found in tabular/export data."""
    raw: dict
    normalized: dict
    source: dict


class CiteLocatorArgs(BaseModel):
    """Arguments for validating that a locator round-trips to source text."""
    locator: dict


class FinalizeSummaryArgs(BaseModel):
    """Arguments for producing the final per-file summary."""
    one_paragraph_summary: str
    open_questions: list[str] | None = None


def _read_segment_args(parsed: ParsedFile, args: dict) -> dict:
    """Normalize model-shaped read_segment args into the tool's segment_index contract."""
    if "segment_index" in args:
        return args
    if not args:
        return {"segment_index": 0}

    locator = args.get("locator")
    locator_args = locator if isinstance(locator, dict) else args
    for i, seg in enumerate(parsed.segments):
        if all(seg.locator.get(k) == v for k, v in locator_args.items()):
            return {"segment_index": i}
    return args


def build_tools(parsed: ParsedFile, ws: WorkingState) -> dict[ToolName, StructuredTool]:
    """Build LangChain StructuredTool instances bound to this file and working state."""
    return {
        "search_text": StructuredTool.from_function(
            name="search_text",
            description="Search parsed file segments and return ranked hits with segment_index and locator.",
            args_schema=SearchTextArgs,
            func=lambda query, top_k=3: search_text(parsed, query=query, top_k=top_k),
        ),
        "read_segment": StructuredTool.from_function(
            name="read_segment",
            description="Read the full text and locator for one parsed segment by segment_index.",
            args_schema=ReadSegmentArgs,
            func=lambda segment_index: read_segment(parsed, segment_index=segment_index),
        ),
        "extract_workflow": StructuredTool.from_function(
            name="extract_workflow",
            description="Append a workflow record to the per-file working state.",
            args_schema=ExtractWorkflowArgs,
            func=lambda name, actors, systems, steps, manual_touchpoints, sources: extract_workflow(
                ws,
                name=name,
                actors=actors,
                systems=systems,
                steps=steps,
                manual_touchpoints=manual_touchpoints,
                sources=sources,
            ),
        ),
        "extract_pain_signal": StructuredTool.from_function(
            name="extract_pain_signal",
            description="Append an operational pain signal to the per-file working state.",
            args_schema=ExtractPainSignalArgs,
            func=lambda text, category, sources: extract_pain_signal(
                ws, text=text, category=category, sources=sources,
            ),
        ),
        "extract_lead_row": StructuredTool.from_function(
            name="extract_lead_row",
            description="Append a structured lead row to the per-file working state.",
            args_schema=ExtractLeadRowArgs,
            func=lambda raw, normalized, source: extract_lead_row(
                ws, raw=raw, normalized=normalized, source=source,
            ),
        ),
        "cite_locator": StructuredTool.from_function(
            name="cite_locator",
            description="Validate that a locator can be resolved back to source text.",
            args_schema=CiteLocatorArgs,
            func=lambda locator: cite_locator(parsed, locator=locator),
        ),
        "finalize_summary": StructuredTool.from_function(
            name="finalize_summary",
            description="Finalize the per-file working state into a FileSummary and end the loop.",
            args_schema=FinalizeSummaryArgs,
            func=lambda one_paragraph_summary, open_questions=None: finalize_summary(
                ws,
                one_paragraph_summary=one_paragraph_summary,
                open_questions=open_questions,
            ),
        ),
    }


def dispatch(call: ToolCall, *, parsed: ParsedFile, ws: WorkingState) -> Any:
    """Route ``call`` to its tool implementation; raises ValueError on unknown tool names."""
    name = call.tool
    args = call.args
    if name == "read_segment":
        args = _read_segment_args(parsed, args)

    tool = build_tools(parsed, ws)[name]
    return tool.invoke(args)
