"""Per-file agent for JSON exports (CRM dumps and similar)."""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a JSON export (CRM dump or similar). Segments are leaf values "
    "with RFC 6901 pointer locators: {type: 'json', pointer}. Treat each contact/lead "
    "object as a lead_row by reconstructing it from leaf segments under the same prefix."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
