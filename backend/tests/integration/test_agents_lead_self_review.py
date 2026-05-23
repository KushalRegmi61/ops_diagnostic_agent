"""Integration: self_review_final runs against real Ollama + real parser excerpt."""
from pathlib import Path

import httpx
import pytest

from app.agents.lead.self_review_final import run as self_review_run
from app.config import get_settings
from app.llm import get_provider
from app.parsers.md import parse as md_parse
from app.schemas import (
    Blueprint,
    BlueprintClaim,
    FileSummary,
    IntakeBundle,
    Opportunity,
    Source,
)


def _ollama_up(base_url: str) -> bool:
    """Return True if Ollama responds to GET /api/tags within 2 seconds."""
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_self_review_emits_final_review(tmp_path: Path):
    """self_review.run passes deterministic existence + reachability gates and emits booleans."""
    p = tmp_path / "lead_intake.md"
    p.write_text("# Lead intake\n\nCSRs copy emails into HubSpot manually.\n")
    parsed = md_parse(file_id="f1", file_name="lead_intake.md", path=p)

    src = Source(file_id="f1", file_name="lead_intake.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    claim = BlueprintClaim(text="auto-route inbound leads", sources=[src])
    bp = Blueprint(
        opportunity_ref=0, summary=claim, steps=[claim],
        required_systems=[claim], success_metrics=[claim], risks=[claim],
    )
    bundle = IntakeBundle(
        workflows=[], pain_signals=[], lead_rows=[],
        contradictions=[], file_index=[src], extraction_errors=[],
    )
    op = Opportunity(
        workflow_name="lead intake", bottleneck_refs=[0],
        pain_score=8, roi_score=8, effort_score=3, risk_score=2,
        hours_saved_per_week=10.0, response_time_impact="-50%",
        rationale="auto routing", sources=[src],
    )
    fs = FileSummary(
        file_id="f1", file_name="lead_intake.md",
        one_paragraph_summary="manual lead copy", key_workflows=[],
        key_pain_signals=[], lead_rows=[],
        open_questions=["What is the lead volume per week?"], agent_notes="",
    )

    get_provider.cache_clear()
    review = self_review_run(
        provider=get_provider(),
        blueprint=bp,
        bundle=bundle,
        selected=op,
        opportunities=[op],
        file_summaries={"f1": fs},
        parsed_files={"f1": parsed},
        revised_once=False,
    )

    assert review.citation_existence_ok is True
    assert review.citation_reachability_ok is True
    assert review.revised_once is False
    # LLM judgment is non-deterministic but must produce booleans + non-empty detail.
    assert isinstance(review.no_silent_drops_ok, bool)
    assert isinstance(review.internal_consistency_ok, bool)
    assert review.detail
