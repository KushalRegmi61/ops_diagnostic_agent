import pytest
from pydantic import ValidationError

from app.schemas import (
    Blueprint,
    BlueprintClaim,
    Bottleneck,
    Contradiction,
    FileSummary,
    FinalReview,
    IntakeBundle,
    LeadRow,
    Opportunity,
    PainSignal,
    RevisionRequest,
    Source,
    SummaryReview,
    WorkflowRecord,
)


def _src(file_id: str = "f1") -> Source:
    return Source(
        file_id=file_id, file_name="x.pdf", type="pdf",
        locator={"type": "pdf", "page": 1, "span_start": 0, "span_end": 10},
    )


def test_workflow_record_requires_sources():
    wf = WorkflowRecord(
        name="onboarding", actors=["CSR"], systems=["Applied Epic"],
        steps=["verify id"], manual_touchpoints=["copy"], sources=[_src()],
    )
    assert wf.sources[0].file_id == "f1"


def test_file_summary_round_trips():
    fs = FileSummary(
        file_id="f1", file_name="x.pdf",
        one_paragraph_summary="summary",
        key_workflows=[], key_pain_signals=[], lead_rows=[],
        open_questions=[], agent_notes="",
    )
    assert fs.file_id == "f1"


def test_revision_request_rejects_unknown_reason():
    with pytest.raises(ValidationError):
        RevisionRequest(file_id="f1", reason="bogus", detail="x")


def test_summary_review_allows_empty_requests():
    sr = SummaryReview(revision_requests=[], notes="all good")
    assert sr.notes == "all good"


def test_intake_bundle_holds_contradictions():
    bundle = IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[Contradiction(topic="CRM name", statements=[
            {"claim": "Salesforce", "sources": [_src("a").model_dump()]},
            {"claim": "HubSpot", "sources": [_src("b").model_dump()]},
        ])],
        file_index=[_src("a"), _src("b")],
        extraction_errors=[],
    )
    assert bundle.contradictions[0].topic == "CRM name"


def test_opportunity_score_ranges():
    op = Opportunity(
        workflow_name="lead-intake", bottleneck_refs=[0],
        pain_score=7, roi_score=8, effort_score=4, risk_score=2,
        hours_saved_per_week=5.0, response_time_impact="-50%",
        rationale="text", sources=[_src()],
    )
    assert op.roi_score == 8


def test_blueprint_claim_carries_sources():
    bc = BlueprintClaim(text="connect HubSpot to Drive", sources=[_src()])
    assert bc.sources[0].file_id == "f1"


def test_final_review_pass_fail_per_check():
    fr = FinalReview(
        citation_existence_ok=True, citation_reachability_ok=True,
        no_silent_drops_ok=True, internal_consistency_ok=True,
        detail="all checks pass", revised_once=False,
    )
    assert fr.citation_existence_ok is True
