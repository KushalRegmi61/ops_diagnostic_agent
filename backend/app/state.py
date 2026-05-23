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
