"""Per-file ReAct agent for tabular files (CSV and XLSX).

Prompt suffix steers the agent toward extracting diagnostically useful
``lead_row`` records and emitting pain signals for stalled stages; supports
both flat CSV and sheet-scoped XLSX locators.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "Table: likely lead/opportunity rows with status or timing. "
    "Prioritize stalled, missing-owner, high-value, or representative rows. "
    "Locators: CSV {type: 'table', row_index}; XLSX {type: 'xlsx', sheet, row_index}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    """Drive the ReAct loop for a parsed CSV/XLSX file; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
