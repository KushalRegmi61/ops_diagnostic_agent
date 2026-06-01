"""Typed boundaries — the contract every layer of the pipeline obeys.

Defines the 8-member Source locator discriminated union, per-file agent
outputs (FileSummary and its parts), reviewer outputs, the synthesized
IntakeBundle, the diagnostic chain outputs (Bottleneck/Opportunity/
Blueprint), and the FinalReview emitted by self_review_final. The
citation invariant — every Source must round-trip through
`app.parsers.excerpt(parsed, locator)` to non-empty text — is enforced
against these schemas.
"""
from typing import Literal, Union

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    """Locator into a parsed PDF: page index plus character span."""

    type: Literal["pdf"] = "pdf"
    page: int
    span_start: int
    span_end: int


class DocxLocator(BaseModel):
    """Locator into a parsed DOCX: paragraph index plus character span."""

    type: Literal["docx"] = "docx"
    paragraph_index: int
    span_start: int
    span_end: int


class TextLocator(BaseModel):
    """Locator into plain-text / markdown content: inclusive line range."""

    type: Literal["text"] = "text"
    line_start: int
    line_end: int


class TranscriptLocator(BaseModel):
    """Locator into a VTT/SRT transcript: line range plus timestamps."""

    type: Literal["transcript"] = "transcript"
    line_start: int
    line_end: int
    ts_start: str
    ts_end: str


class TableLocator(BaseModel):
    """Locator into a CSV table: zero-indexed row."""

    type: Literal["table"] = "table"
    row_index: int


class XlsxLocator(BaseModel):
    """Locator into an XLSX workbook: sheet name plus row index."""

    type: Literal["xlsx"] = "xlsx"
    sheet: str
    row_index: int


class MboxLocator(BaseModel):
    """Locator into an MBOX archive: message id plus header/body section."""

    type: Literal["mbox"] = "mbox"
    message_id: str
    section: Literal["header", "body"] = "body"


class JsonLocator(BaseModel):
    """Locator into a JSON document via RFC 6901 JSON Pointer."""

    type: Literal["json"] = "json"
    pointer: str  # RFC 6901


AnyLocator = Union[
    PdfLocator, DocxLocator, TextLocator, TranscriptLocator,
    TableLocator, XlsxLocator, MboxLocator, JsonLocator,
]


FileType = Literal[
    "pdf", "docx", "md", "txt",
    "transcript_vtt", "transcript_srt",
    "csv", "xlsx", "mbox", "json",
]


class Source(BaseModel):
    """A citation: file identity plus a typed discriminated-union locator."""

    file_id: str
    file_name: str
    type: FileType
    locator: AnyLocator


class ParsedSegment(BaseModel):
    """One addressable unit of parsed content — text plus the locator that points back to it."""

    text: str
    locator: dict


class ParsedFile(BaseModel):
    """A fully parsed file: identity, type, and the ordered list of ParsedSegments."""

    file_id: str
    file_name: str
    type: FileType
    segments: list[ParsedSegment]


class ExtractionError(BaseModel):
    """A structured failure surfaced from parsing, per-file agent run, review, or graph nodes."""

    file_id: str
    stage: Literal[
        "parse", "agent", "review",
        "synthesis", "review_summaries", "workflow_map", "bottleneck_detect",
        "roi_score", "fastest_win_select", "solution_blueprint", "self_review_final",
        "per_file_react",
    ]
    message: str


class FileRef(BaseModel):
    """Lightweight reference to an uploaded file, returned by the upload endpoint."""

    file_id: str
    file_name: str
    mime_type: str
    blob_path: str
    parser_status: Literal["ok", "error", "pending"]


# ---- Per-file agent output types ----

class WorkflowRecord(BaseModel):
    """A workflow extracted from a file: name, actors, systems, steps, manual touchpoints, citations."""

    name: str
    actors: list[str]
    systems: list[str]
    steps: list[str]
    manual_touchpoints: list[str]
    sources: list[Source]


class PainSignal(BaseModel):
    """An operational pain point with category and supporting citations."""

    text: str
    category: Literal["delay", "error", "repetition", "handoff",
                      "missing_data", "visibility_gap", "revenue_leak"]
    sources: list[Source]


class KVPair(BaseModel):
    """A single key/value pair — used in place of free-form dicts so OpenAI strict schemas validate."""

    key: str
    value: str


class LeadRow(BaseModel):
    """A normalized lead row (e.g. from a CSV) with its raw form and source citation."""

    raw: list[KVPair]
    normalized: list[KVPair]
    source: Source


class FileSummary(BaseModel):
    """Per-file agent output: prose summary, workflows, pain signals, lead rows, open questions."""

    file_id: str
    file_name: str
    one_paragraph_summary: str
    key_workflows: list[WorkflowRecord]
    key_pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    open_questions: list[str]
    agent_notes: str


class AgentTurn(BaseModel):
    """The model's per-turn self-direction, carried on every tool call.

    Holds reasoning intent only — never locators or citations. Fields default to
    empty so a tool call that omits them never crashes (variance-tolerant)."""

    open_gap: str = ""           # what is still missing — the gap chased this turn
    plan_next: str = ""          # the single next step and why
    ready_to_finalize: bool = False  # advisory self-assessment of coverage


# ---- Reviewer types ----

class RevisionRequest(BaseModel):
    """A reviewer's request to re-run a specific file with a categorized reason."""

    file_id: str
    reason: Literal["missing_info", "contradiction", "weak_citation",
                    "ignored_open_question", "schema_drift"]
    detail: str


class SummaryReview(BaseModel):
    """review_summaries output — set of revision requests plus free-form notes."""

    revision_requests: list[RevisionRequest]
    notes: str


# ---- Synthesis types ----

class ContradictionStatement(BaseModel):
    """One side of a contradiction: a claim plus the sources that back it."""

    claim: str
    sources: list[Source]


class Contradiction(BaseModel):
    """A cross-file contradiction: topic plus the conflicting statements."""

    topic: str
    statements: list[ContradictionStatement]


class IntakeBundle(BaseModel):
    """Cross-file synthesis — merged workflows, pain signals, leads, contradictions, file index."""

    workflows: list[WorkflowRecord]
    pain_signals: list[PainSignal]
    lead_rows: list[LeadRow]
    contradictions: list[Contradiction]
    file_index: list[Source]
    extraction_errors: list[ExtractionError]


# ---- Diagnostic chain types ----

class Bottleneck(BaseModel):
    """A detected bottleneck inside a workflow with its signal category and impact."""

    workflow_name: str
    signal: Literal["delay", "error", "repetition", "handoff",
                    "missing_data", "visibility_gap", "revenue_leak"]
    impact: str
    sources: list[Source]


class Opportunity(BaseModel):
    """A scored automation opportunity: pain/ROI/effort/risk plus quantified savings."""

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
    """A single claim inside the Blueprint, always carrying its supporting Sources."""

    text: str
    sources: list[Source]


class Blueprint(BaseModel):
    """The final automation blueprint for the selected fastest-win opportunity."""

    opportunity_ref: int
    summary: BlueprintClaim
    steps: list[BlueprintClaim]
    required_systems: list[BlueprintClaim]
    success_metrics: list[BlueprintClaim]
    risks: list[BlueprintClaim]


# ---- Self-review type ----

class FinalReview(BaseModel):
    """self_review_final output: existence/reachability/consistency gates plus detail."""

    citation_existence_ok: bool
    citation_reachability_ok: bool
    no_silent_drops_ok: bool
    internal_consistency_ok: bool
    detail: str
    revised_once: bool


class RunContext(BaseModel):
    """Operator-provided steering carried through the parent graph and per-file subgraph.

    Today carries only ``user_context``. Designed to absorb future structured
    fields (examples, glossary, exclude lists, weights) without re-plumbing
    every node signature.
    """

    user_context: str | None = Field(
        default=None,
        max_length=2000,
        description="Free-text operator priorities. Never cited as a Source.",
    )

    def has_steering(self) -> bool:
        """Return True iff at least one steering field is populated (non-whitespace)."""
        return bool(self.user_context and self.user_context.strip())
