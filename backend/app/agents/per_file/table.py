"""Per-file agent for tabular files (CSV and XLSX)."""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a TABLE (CSV or XLSX). Likely contents: a lead list with stage and timing. "
    "For EVERY row, call extract_lead_row with {raw, normalized, source}. "
    "Locators: {type: 'table', row_index} for CSV, {type: 'xlsx', sheet, row_index} for XLSX. "
    "Also emit key_pain_signals for stages where rows have stalled (e.g. days_in_stage > 14)."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
