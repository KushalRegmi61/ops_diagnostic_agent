import pytest

from app.llm import get_provider


def test_factory_returns_ollama_by_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    get_provider.cache_clear()
    p = get_provider()
    assert p.name == "ollama"


def test_factory_rejects_openai_without_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    get_provider.cache_clear()
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_provider()
