from app.observability import langfuse_client


def test_langfuse_client_returns_none_when_keys_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    langfuse_client.cache_clear()
    assert langfuse_client() is None
