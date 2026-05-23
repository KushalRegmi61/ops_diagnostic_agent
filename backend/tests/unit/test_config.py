"""Settings loading + validation from environment variables."""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_loads_from_env(monkeypatch):
    """Settings reads provider, DB URL, and Ollama config from env."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    s = Settings()
    assert s.llm_provider == "ollama"
    assert s.database_url == "sqlite:///./test.db"
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.ollama_model == "llama3.1:8b"


def test_settings_rejects_unknown_provider(monkeypatch):
    """An unsupported LLM_PROVIDER value raises ValidationError."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_loads_redis_and_langfuse(monkeypatch):
    """Settings carries Redis URL plus Langfuse keys/base URL through unchanged."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    s = Settings()
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.langgraph_checkpointer == "redis"
    assert s.langgraph_checkpoint_namespace == "ops_diagnostic"
    assert s.langfuse_public_key == "pk_test"
    assert s.langfuse_secret_key == "sk_test"
    assert s.langfuse_base_url.startswith("https://")
