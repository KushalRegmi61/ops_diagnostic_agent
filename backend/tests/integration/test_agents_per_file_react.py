"""ReAct loop integration: drive run_react_loop against real Ollama + md parser."""
import httpx
import pytest
from pathlib import Path

from app.agents.per_file._react_loop import run_react_loop
from app.config import get_settings
from app.llm import get_provider
from app.parsers import md as md_parser


def _ollama_up(base_url: str) -> bool:
    """Return True if Ollama responds to GET /api/tags within 2 seconds."""
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


SETTINGS = get_settings()
pytestmark = pytest.mark.skipif(
    not _ollama_up(SETTINGS.ollama_base_url),
    reason="Ollama not reachable",
)


def test_react_loop_produces_file_summary_from_markdown():
    """run_react_loop drives the agent end-to-end and every emitted Source round-trips."""
    fixture = Path(__file__).parent.parent / "fixtures" / "notes.md"
    parsed = md_parser.parse(file_id="f1", file_name="notes.md", path=fixture)
    get_provider.cache_clear()
    provider = get_provider()
    fs = run_react_loop(
        provider=provider,
        parsed=parsed,
        prompt_suffix="This is a Markdown notes file from an insurance ops discovery call.",
        iteration_cap=6,
    )
    assert fs.file_id == "f1"
    assert isinstance(fs.one_paragraph_summary, str)
    # Every Source attached anywhere must roundtrip through the parser.
    from app.agents.per_file._tools.cite_locator import cite_locator
    for wf in fs.key_workflows:
        for src in wf.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
    for ps in fs.key_pain_signals:
        for src in ps.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
