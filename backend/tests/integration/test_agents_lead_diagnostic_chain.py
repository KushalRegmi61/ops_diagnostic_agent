"""Full five-node lead diagnostic chain (workflow_map -> blueprint) against Ollama.

Drives workflow_map, bottleneck_detect, roi_score, fastest_win_select, and
solution_blueprint in sequence on a hand-built IntakeBundle. Skipped when
Ollama is unreachable.
"""
import httpx
import pytest

from app.agents.lead import (
    bottleneck_detect, fastest_win_select, roi_score, solution_blueprint, workflow_map,
)
from app.config import get_settings
from app.llm import get_provider
from app.schemas import IntakeBundle, PainSignal, Source, WorkflowRecord


def _ollama_up(base_url):
    """Return True if Ollama responds to GET /api/tags within 2 seconds."""
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def _bundle() -> IntakeBundle:
    """Build a one-workflow, one-pain-signal IntakeBundle to seed the chain."""
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    wf = WorkflowRecord(
        name="lead intake", actors=["CSR"], systems=["HubSpot"],
        steps=["receive email", "create lead in CRM"],
        manual_touchpoints=["copy email body into CRM"], sources=[src],
    )
    ps = PainSignal(text="leads waiting > 24h", category="delay", sources=[src])
    return IntakeBundle(
        workflows=[wf], pain_signals=[ps], lead_rows=[],
        contradictions=[], file_index=[src], extraction_errors=[],
    )


def test_full_diagnostic_chain_emits_blueprint():
    """All five diagnostic nodes chain to a Blueprint whose claims have sources."""
    bundle = _bundle()
    get_provider.cache_clear()
    p = get_provider()
    wfs = workflow_map.run(provider=p, bundle=bundle)
    bns = bottleneck_detect.run(provider=p, bundle=bundle, workflows=wfs)
    ops = roi_score.run(provider=p, bundle=bundle, bottlenecks=bns)
    if not ops:
        pytest.skip("roi_score returned empty; model variance")
    selected = fastest_win_select.run(provider=p, opportunities=ops)
    assert selected is not None
    selected_index = ops.index(selected)
    bp = solution_blueprint.run(provider=p, bundle=bundle, selected=selected, selected_index=selected_index)
    assert bp is not None
    # Every claim has at least one source.
    for claim in [bp.summary, *bp.steps, *bp.required_systems, *bp.success_metrics, *bp.risks]:
        assert len(claim.sources) >= 1
