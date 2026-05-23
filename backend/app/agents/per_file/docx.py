"""Per-file ReAct agent for Word DOCX files.

Thin wrapper that injects a DOCX-specific prompt suffix (paragraph-indexed
locators, likely SOP/onboarding content) and delegates to ``run_react_loop``.
"""
from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm.base import LLMProvider
from app.schemas import FileSummary, ParsedFile

_SUFFIX = (
    "This file is a Word DOCX. Likely contents: SOPs, onboarding docs, internal policies. "
    "Locators are {type: 'docx', paragraph_index, span_start, span_end}."
)


def run(*, provider: LLMProvider, parsed: ParsedFile, on_tool_call=None) -> FileSummary:
    """Drive the ReAct loop for a parsed DOCX; returns the produced FileSummary."""
    cap = get_settings().per_file_iteration_cap
    return run_react_loop(
        provider=provider, parsed=parsed,
        prompt_suffix=_SUFFIX, iteration_cap=cap, on_tool_call=on_tool_call,
    )
