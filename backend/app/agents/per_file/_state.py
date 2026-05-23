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
