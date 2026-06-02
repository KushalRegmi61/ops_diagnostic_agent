"""WorkingState / ProgressState dataclass for the per-file ReAct loop.

Holds the mutable findings (workflows, pain signals, lead rows, open questions)
that tools append across iterations, plus the deterministic working-memory the
loop maintains: coverage map, budget, query log, plan, and stall bookkeeping.
``finalize_summary`` (or force-finalize) turns this scratch into a FileSummary.
"""
from dataclasses import dataclass, field

from app.schemas import AgentTurn, LeadRow, PainSignal, WorkflowRecord


@dataclass
class WorkingState:
    """The ReAct agent's mutable working memory. Becomes a FileSummary at finalize."""
    file_id: str
    file_name: str
    workflows: list[WorkflowRecord] = field(default_factory=list)
    pain_signals: list[PainSignal] = field(default_factory=list)
    lead_rows: list[LeadRow] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    notes: str = ""
    iteration: int = 0

    # --- deterministic working-memory (Increment #1) ---
    total_segments: int = 0
    iteration_cap: int = 0
    segments_visited: list[int] = field(default_factory=list)
    queries_run: list[str] = field(default_factory=list)
    coverage_frontier: int = 0
    plan: list[str] = field(default_factory=list)
    last_signature: str | None = None
    stall_count: int = 0
    findings_at_turn: list[int] = field(default_factory=list)

    # --- model-written layer (Increment #1.5) ---
    last_turn: AgentTurn | None = None
    turn_log: list[AgentTurn] = field(default_factory=list)

    @property
    def steps_remaining(self) -> int:
        """Turns left before force-finalize; floored at zero."""
        return max(0, self.iteration_cap - self.iteration)
