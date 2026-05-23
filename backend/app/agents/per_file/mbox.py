"""Per-file ReAct agent for MBOX email exports.

Each parsed segment is one message body; the prompt suffix nudges the agent
to treat qualifying messages as lead rows with ``mbox`` message-id locators.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is an MBOX email export. Each segment is one message body. "
    "Treat each message as a potential lead — call extract_lead_row if it is one. "
    "Locators are {type: 'mbox', message_id, section}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    """Drive the ReAct loop for a parsed MBOX file; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
