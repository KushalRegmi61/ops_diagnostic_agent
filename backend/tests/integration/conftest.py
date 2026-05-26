"""Integration test defaults."""
import pytest

from app.llm import get_provider


@pytest.fixture(autouse=True)
def _default_integration_provider(monkeypatch):
    """Integration tests exercise the local Ollama path unless they instantiate a provider directly."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_provider.cache_clear()
    yield
    get_provider.cache_clear()
