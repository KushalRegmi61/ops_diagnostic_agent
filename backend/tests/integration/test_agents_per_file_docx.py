import httpx
import pytest
from pathlib import Path

from app.agents.per_file import docx as docx_agent
from app.agents.per_file._tools.cite_locator import cite_locator
from app.config import get_settings
from app.llm import get_provider
from app.parsers import docx as docx_parser


def _ollama_up(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url}/api/tags", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_up(get_settings().ollama_base_url),
    reason="Ollama not reachable",
)


def test_per_file_docx_emits_valid_file_summary():
    fixture = Path(__file__).parent.parent / "fixtures" / "sop.docx"
    parsed = docx_parser.parse(file_id="f1", file_name="sop.docx", path=fixture)
    get_provider.cache_clear()
    fs = docx_agent.run(provider=get_provider(), parsed=parsed)
    assert fs.file_id == "f1"
    for record in fs.key_workflows + fs.key_pain_signals:
        for src in record.sources:
            assert cite_locator(parsed, locator=src.locator)["valid"] is True
