"""LangGraph state TypedDict shared by every node in the parent workflow.

`DiagnosticState` is the 14-key state object threaded through the graph. It
is Redis-checkpointable thanks to `app._langgraph_pydantic_patch`, which
teaches the JSON serializer how to dump Pydantic BaseModel values.

`errors` is annotated with `operator.add` so LangGraph's reducer accumulates
ExtractionError records across nodes automatically — each node returns
`{"errors": [new]}` and the framework merges via list addition.
"""
import operator
from typing import Annotated, TypedDict

from app.schemas import (
    Blueprint,
    Bottleneck,
    ExtractionError,
    FileRef,
    FileSummary,
    FinalReview,
    IntakeBundle,
    Opportunity,
    RunContext,
    SummaryReview,
    WorkflowRecord,
)


def merge_file_summaries(
    left: dict[str, FileSummary] | None,
    right: dict[str, FileSummary] | None,
) -> dict[str, FileSummary]:
    """Reducer for file_summaries across parallel per-file branches.

    Each branch returns {file_id: summary}; later writes (right) win per
    file_id so a redo pass overwrites the prior summary for the same file.
    """
    return {**(left or {}), **(right or {})}


class DiagnosticState(TypedDict):
    """Shared state for the parent LangGraph workflow — one entry per pipeline output."""

    run_id: str
    files: list[FileRef]
    run_context: RunContext | None
    file_summaries: Annotated[dict[str, FileSummary], merge_file_summaries]
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
    errors: Annotated[list[ExtractionError], operator.add]
