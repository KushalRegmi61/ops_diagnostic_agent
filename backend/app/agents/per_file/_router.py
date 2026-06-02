"""Typed tool dispatcher for the per-file ReAct loop.

Parses the LLM's ``{tool, args}`` reply into a ToolCall and routes it to the
matching function under ``_tools/``. Unknown tool names raise so the loop can
log the failure and continue rather than silently dropping the call.
"""
from typing import Any, Callable, Literal

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


TURN_FIELDS = ("open_gap", "plan_next", "ready_to_finalize")


class _TurnMixin(BaseModel):
    """AgentTurn reasoning fields mixed into every tool's args (stripped before dispatch).

    Mirrors ``app.schemas.AgentTurn``; kept in sync via ``TURN_FIELDS``."""
    open_gap: str = ""
    plan_next: str = ""
    ready_to_finalize: bool = False


def _strip_turn(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a tool func so AgentTurn reasoning fields are dropped before dispatch."""
    def wrapped(**kwargs):
        """Pop the turn fields then call the wrapped tool func with the remaining args."""
        for f in TURN_FIELDS:
            kwargs.pop(f, None)
        return fn(**kwargs)
    return wrapped


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


class SearchTextArgs(_TurnMixin):
    """Arguments for searching over parsed file segments."""
    query: str
    top_k: int = 3


class ReadSegmentArgs(_TurnMixin):
    """Arguments for reading one parsed segment by its zero-based index."""
    segment_index: int


class ExtractWorkflowArgs(_TurnMixin):
    """Arguments for recording a workflow found in the file."""
    name: str
    actors: list[str]
    systems: list[str]
    steps: list[str]
    manual_touchpoints: list[str]
    sources: list[dict]


class ExtractPainSignalArgs(_TurnMixin):
    """Arguments for recording a pain signal found in the file."""
    text: str
    category: Literal["delay", "error", "repetition", "handoff", "missing_data", "visibility_gap", "revenue_leak"]
    sources: list[dict]


class ExtractLeadRowArgs(_TurnMixin):
    """Arguments for recording a structured lead row found in tabular/export data."""
    raw: dict
    normalized: dict
    source: dict


class CiteLocatorArgs(_TurnMixin):
    """Arguments for validating that a locator round-trips to source text."""
    locator: dict


class FinalizeSummaryArgs(_TurnMixin):
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


def _cite_locator_with_source(parsed: ParsedFile, locator: dict) -> dict:
    """Return validation result plus the reusable Source-shaped citation."""
    result = cite_locator(parsed, locator=locator)
    if result.get("valid") is True:
        result["source"] = {
            "file_id": parsed.file_id,
            "file_name": parsed.file_name,
            "type": parsed.type,
            "locator": locator,
        }
    return result


def build_tools(parsed: ParsedFile, ws: WorkingState, *, agent_mode: bool = False) -> dict[ToolName, StructuredTool]:
    """Build LangChain StructuredTool instances bound to this file and working state."""
    def _finalize(one_paragraph_summary, open_questions=None):
        summary = finalize_summary(
            ws,
            one_paragraph_summary=one_paragraph_summary,
            open_questions=open_questions,
        )
        return summary.model_dump(mode="json") if agent_mode else summary

    return {
        "search_text": StructuredTool.from_function(
            name="search_text",
            description="Search parsed file segments and return ranked hits with segment_index and locator.",
            args_schema=SearchTextArgs,
            func=_strip_turn(lambda query, top_k=3: search_text(parsed, query=query, top_k=top_k)),
        ),
        "read_segment": StructuredTool.from_function(
            name="read_segment",
            description="Read the full text and locator for one parsed segment by segment_index.",
            args_schema=ReadSegmentArgs,
            func=_strip_turn(lambda segment_index: read_segment(parsed, segment_index=segment_index)),
        ),
        "extract_workflow": StructuredTool.from_function(
            name="extract_workflow",
            description="Append a workflow record to the per-file working state.",
            args_schema=ExtractWorkflowArgs,
            func=_strip_turn(lambda name, actors, systems, steps, manual_touchpoints, sources: extract_workflow(
                ws,
                name=name,
                actors=actors,
                systems=systems,
                steps=steps,
                manual_touchpoints=manual_touchpoints,
                sources=sources,
            )),
        ),
        "extract_pain_signal": StructuredTool.from_function(
            name="extract_pain_signal",
            description="Append an operational pain signal to the per-file working state.",
            args_schema=ExtractPainSignalArgs,
            func=_strip_turn(lambda text, category, sources: extract_pain_signal(
                ws, text=text, category=category, sources=sources,
            )),
        ),
        "extract_lead_row": StructuredTool.from_function(
            name="extract_lead_row",
            description="Append a structured lead row to the per-file working state.",
            args_schema=ExtractLeadRowArgs,
            func=_strip_turn(lambda raw, normalized, source: extract_lead_row(
                ws, raw=raw, normalized=normalized, source=source,
            )),
        ),
        "cite_locator": StructuredTool.from_function(
            name="cite_locator",
            description="Validate that a locator can be resolved and return a reusable source object.",
            args_schema=CiteLocatorArgs,
            func=_strip_turn(lambda locator: _cite_locator_with_source(parsed, locator)),
        ),
        "finalize_summary": StructuredTool.from_function(
            name="finalize_summary",
            description="Finalize the per-file working state into a FileSummary and end the loop.",
            args_schema=FinalizeSummaryArgs,
            func=_strip_turn(_finalize),
            return_direct=True,
        ),
    }


def dispatch(call: ToolCall, *, parsed: ParsedFile, ws: WorkingState) -> Any:
    """Route ``call`` to its tool implementation, stripping AgentTurn reasoning fields first; raises ValueError on unknown tool names."""
    name = call.tool
    args = call.args
    # Strip here too (not only in _strip_turn): this legacy direct-dispatch path
    # bypasses the bound StructuredTool funcs, so it needs its own guard.
    args = {k: v for k, v in args.items() if k not in TURN_FIELDS}
    if name == "read_segment":
        args = _read_segment_args(parsed, args)

    tool = build_tools(parsed, ws)[name]
    return tool.invoke(args)
