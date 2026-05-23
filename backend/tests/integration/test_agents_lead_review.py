import httpx
import pytest

from app.agents.lead import review_summaries
from app.config import get_settings
from app.llm import get_provider
from app.schemas import FileSummary, PainSignal, Source


def _ollama_up(base_url):
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_reviewer_returns_valid_summary_review():
    src = Source(file_id="f1", file_name="x.md", type="md",
                 locator={"type": "text", "line_start": 1, "line_end": 1})
    pain = PainSignal(text="leads are slow", category="delay", sources=[])  # crafted gap: no sources
    fs = FileSummary(
        file_id="f1", file_name="x.md",
        one_paragraph_summary="a summary",
        key_workflows=[], key_pain_signals=[pain], lead_rows=[],
        open_questions=[], agent_notes="",
    )
    get_provider.cache_clear()
    sr = review_summaries.run(provider=get_provider(), file_summaries={"f1": fs})
    # Model variance can produce 0 or N requests — the assertion is structural,
    # not behavioral, because temperature=0 + small models still vary.
    assert sr.notes is not None
    assert isinstance(sr.revision_requests, list)
