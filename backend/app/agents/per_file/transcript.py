"""Per-file agent for meeting transcripts (VTT and SRT)."""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a meeting transcript (VTT or SRT). Likely contents: "
    "founder/CSR discovery calls describing operational pain. "
    "Locators carry timestamps: {type: 'transcript', line_start, line_end, ts_start, ts_end}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
