"""Per-file ReAct agent for MBOX email exports.

Each parsed segment is one message body; the prompt suffix nudges the agent
to treat qualifying messages as lead rows with ``mbox`` message-id locators.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "MBOX: each segment is one email body. "
    "Prioritize quote requests, lead intent, missing follow-up, and handoffs. "
    "Locator: {type: 'mbox', message_id, section}."
)


def run(
    *,
    provider: LLMProvider,
    parsed: ParsedFile,
    on_tool_call=None,
    run_id: str | None = None,
    trace_name: str | None = None,
) -> FileSummary:
    """Drive the ReAct loop for a parsed MBOX file; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
        run_id=run_id, trace_name=trace_name,
    )
