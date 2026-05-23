"""Per-file agent for Markdown and plain-text files."""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a Markdown or plain-text notes file. Likely contents: "
    "meeting notes, discovery-call summaries, internal memos. "
    "Locators are {type: 'text', line_start, line_end}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
