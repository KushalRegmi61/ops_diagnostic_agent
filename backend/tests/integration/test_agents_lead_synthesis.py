"""synthesis lead node against real Ollama: file summaries -> IntakeBundle."""
import httpx
import pytest

from app.agents.lead import synthesis
from app.config import get_settings
from app.llm import get_provider
from app.schemas import FileSummary, PainSignal, Source


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


def test_synthesis_returns_valid_intake_bundle():
    """synthesis.run returns a structurally valid IntakeBundle with list slots."""
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    fs = FileSummary(
        file_id="f1", file_name="x.md",
        one_paragraph_summary="slow leads",
        key_workflows=[],
        key_pain_signals=[PainSignal(text="leads slow", category="delay", sources=[src])],
        lead_rows=[], open_questions=[], agent_notes="",
    )
    get_provider.cache_clear()
    bundle = synthesis.run(provider=get_provider(), file_summaries={"f1": fs})
    # Structural assertions — we know the synthesizer produced a valid IntakeBundle.
    # We don't assert specific carryover because model variance can drop or keep elements.
    assert isinstance(bundle.workflows, list)
    assert isinstance(bundle.pain_signals, list)
    assert isinstance(bundle.file_index, list)
