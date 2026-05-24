"""Tool for ending the per-file ReAct loop and returning the file summary.

The extraction tools build up a mutable ``WorkingState`` during the loop:
workflows, pain signals, lead rows, open questions, and notes. When the LLM has
collected enough evidence, it calls ``finalize_summary`` with a concise
one-paragraph summary and any unresolved questions.

This tool freezes the working state into a ``FileSummary``. The ReAct loop
recognizes that return type, stops iterating, and hands the summary to the
lead-level review and synthesis agents.
"""
from app.agents.per_file._state import WorkingState
from app.schemas import FileSummary


def finalize_summary(ws: WorkingState, *, one_paragraph_summary: str, open_questions: list[str] | None = None) -> FileSummary:
    """Freeze accumulated findings into the ``FileSummary`` returned for one file."""
    return FileSummary(
        file_id=ws.file_id,
        file_name=ws.file_name,
        one_paragraph_summary=one_paragraph_summary,
        key_workflows=ws.workflows,
        key_pain_signals=ws.pain_signals,
        lead_rows=ws.lead_rows,
        open_questions=open_questions or ws.open_questions,
        agent_notes=ws.notes,
    )
