"""Per-file ReAct agent for JSON exports (CRM dumps and similar).

Segments are leaf values addressed by RFC 6901 pointers; the prompt suffix
guides the agent to reconstruct contact/lead objects from sibling leaves.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile, RunContext

_SUFFIX = (
    "JSON: likely CRM/export leaves. "
    "Prioritize reconstructing lead/contact objects from sibling pointers. "
    "Locator: {type: 'json', pointer}."
)


def run(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    on_tool_call=None,
    run_id: str | None = None,
    trace_name: str | None = None,
    user_context: str | None = None,
) -> FileSummary:
    """Drive the ReAct loop for a parsed JSON file; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
        run_id=run_id, trace_name=trace_name,
        run_context=RunContext(user_context=user_context) if user_context else None,
    )
