"""Per-file ReAct agent for meeting transcripts (VTT and SRT).

Uses a transcript-specific prompt suffix carrying timestamp-bearing locators
so cited excerpts can be linked back to a moment in the recording.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "Transcript: likely discovery-call pain, roles, handoffs, and quotes. "
    "Prioritize speaker-stated problems and timestamps. "
    "Locator: {type: 'transcript', line_start, line_end, ts_start, ts_end}."
)


def run(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    on_tool_call=None,
    run_id: str | None = None,
    trace_name: str | None = None,
) -> FileSummary:
    """Drive the ReAct loop for a parsed VTT/SRT transcript; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
        run_id=run_id, trace_name=trace_name,
    )
