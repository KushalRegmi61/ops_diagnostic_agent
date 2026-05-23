import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_loads_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    s = Settings()
    assert s.llm_provider == "ollama"
    assert s.database_url == "sqlite:///./test.db"
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "llama3.1:8b"


def test_settings_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    with pytest.raises(ValidationError):
        Settings()
