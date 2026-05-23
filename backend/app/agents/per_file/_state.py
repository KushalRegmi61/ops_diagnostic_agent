"""WorkingState dataclass for the per-file ReAct loop.

Holds the mutable findings (workflows, pain signals, lead rows, open questions)
that tools append to across iterations. ``finalize_summary`` turns this scratch
into a FileSummary; the iteration counter is used by the loop for its budget.
"""
from dataclasses import dataclass, field

from app.schemas import LeadRow, PainSignal, WorkflowRecord


@dataclass
class WorkingState:
    """The ReAct agent's mutable scratchpad. Becomes a FileSummary at finalize_summary."""
    file_id: str
    file_name: str
    workflows: list[WorkflowRecord] = field(default_factory=list)
    pain_signals: list[PainSignal] = field(default_factory=list)
    lead_rows: list[LeadRow] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    notes: str = ""
    iteration: int = 0
