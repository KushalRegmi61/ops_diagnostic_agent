"""LangGraph state TypedDict shared by every node in the parent workflow.

`DiagnosticState` is the 14-key state object threaded through the graph. It
is Redis-checkpointable thanks to `app._langgraph_pydantic_patch`, which
teaches the JSON serializer how to dump Pydantic BaseModel values.
"""
from typing import TypedDict

from app.schemas import (
    Blueprint,
    Bottleneck,
    ExtractionError,
    FileRef,
    FileSummary,
    FinalReview,
    IntakeBundle,
    Opportunity,
    SummaryReview,
    WorkflowRecord,
)


class DiagnosticState(TypedDict):
    """Shared state for the parent LangGraph workflow — one entry per pipeline output."""

    run_id: str
    files: list[FileRef]
    file_summaries: dict[str, FileSummary]
    summary_review: SummaryReview | None
    redo_count: int
    bundle: IntakeBundle | None
    workflows: list[WorkflowRecord]
    bottlenecks: list[Bottleneck]
    opportunities: list[Opportunity]
    selected: Opportunity | None
    blueprint: Blueprint | None
    final_review: FinalReview | None
    revision_count: int
    errors: list[ExtractionError]
