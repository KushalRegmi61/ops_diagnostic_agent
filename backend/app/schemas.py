from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    type: Literal["pdf"] = "pdf"
    page: int
    span_start: int
    span_end: int


class DocxLocator(BaseModel):
    type: Literal["docx"] = "docx"
    paragraph_index: int
    span_start: int
    span_end: int


class TextLocator(BaseModel):
    type: Literal["text"] = "text"
    line_start: int
    line_end: int


class TranscriptLocator(BaseModel):
    type: Literal["transcript"] = "transcript"
    line_start: int
    line_end: int
    ts_start: str
    ts_end: str


class TableLocator(BaseModel):
    type: Literal["table"] = "table"
    row_index: int


class XlsxLocator(BaseModel):
    type: Literal["xlsx"] = "xlsx"
    sheet: str
    row_index: int


class MboxLocator(BaseModel):
    type: Literal["mbox"] = "mbox"
    message_id: str
    section: Literal["header", "body"] = "body"


class JsonLocator(BaseModel):
    type: Literal["json"] = "json"
    pointer: str  # RFC 6901


AnyLocator = Annotated[
    Union[
        PdfLocator, DocxLocator, TextLocator, TranscriptLocator,
        TableLocator, XlsxLocator, MboxLocator, JsonLocator,
    ],
    Field(discriminator="type"),
]


FileType = Literal[
    "pdf", "docx", "md", "txt",
    "transcript_vtt", "transcript_srt",
    "csv", "xlsx", "mbox", "json",
]


class Source(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    locator: dict


class ParsedSegment(BaseModel):
    text: str
    locator: dict


class ParsedFile(BaseModel):
    file_id: str
    file_name: str
    type: FileType
    segments: list[ParsedSegment]


class ExtractionError(BaseModel):
    file_id: str
    stage: Literal["parse", "agent", "review"]
    message: str


class FileRef(BaseModel):
    file_id: str
    file_name: str
    mime_type: str
    blob_path: str
    parser_status: Literal["ok", "error", "pending"]


# ---- Per-file agent output types ----

class WorkflowRecord(BaseModel):
    name: str
    actors: list[str]
    systems: list[str]
    steps: list[str]
    manual_touchpoints: list[str]
    sources: list[Source]


class PainSignal(BaseModel):
    text: str
    category: Literal["delay", "error", "repetition", "handoff",
                      "missing_data", "visibility_gap", "revenue_leak"]
    sources: list[Source]


class LeadRow(BaseModel):
    raw: dict
    normalized: dict
    source: Source


class FileSummary(BaseModel):
    file_id: str
    file_name: str
    one_paragraph_summary: str
    key_workflows: list[WorkflowRecord]
    key_pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    open_questions: list[str]
    agent_notes: str


# ---- Reviewer types ----

class RevisionRequest(BaseModel):
    file_id: str
    reason: Literal["missing_info", "contradiction", "weak_citation",
                    "ignored_open_question", "schema_drift"]
    detail: str


class SummaryReview(BaseModel):
    revision_requests: list[RevisionRequest]
    notes: str


# ---- Synthesis types ----

class Contradiction(BaseModel):
    topic: str
    statements: list[dict]


class IntakeBundle(BaseModel):
    workflows: list[WorkflowRecord]
    pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    contradictions: list[Contradiction]
    file_index: list[Source]
    extraction_errors: list[ExtractionError]


# ---- Diagnostic chain types ----

class Bottleneck(BaseModel):
    workflow_name: str
    signal: Literal["delay", "error", "repetition", "handoff",
                    "missing_data", "visibility_gap", "revenue_leak"]
    impact: str
    sources: list[Source]


class Opportunity(BaseModel):
    workflow_name: str
    bottleneck_refs: list[int]
    pain_score: int
    roi_score: int
    effort_score: int
    risk_score: int
    hours_saved_per_week: float
    response_time_impact: str
    rationale: str
    sources: list[Source]


class BlueprintClaim(BaseModel):
    text: str
    sources: list[Source]


class Blueprint(BaseModel):
    opportunity_ref: int
    summary: BlueprintClaim
    steps: list[BlueprintClaim]
    required_systems: list[BlueprintClaim]
    success_metrics: list[BlueprintClaim]
    risks: list[BlueprintClaim]


# ---- Self-review type ----

class FinalReview(BaseModel):
    citation_existence_ok: bool
    citation_reachability_ok: bool
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str
    revised_once: bool
