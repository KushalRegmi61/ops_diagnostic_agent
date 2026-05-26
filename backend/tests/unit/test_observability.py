"""Observability: Langfuse client and LangChain callbacks degrade cleanly."""
import sys
import types

from app.config import get_settings
from app.observability import _build_langfuse_handler, langchain_config, langfuse_client


def test_langfuse_client_returns_none_when_keys_missing(monkeypatch):
    """Missing LANGFUSE_PUBLIC_KEY/SECRET_KEY yields a None client (no-op tracing)."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("BLOB_STORE_DIR", "./test_blobs")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    langfuse_client.cache_clear()
    assert langfuse_client() is None


def test_build_langfuse_handler_returns_none_without_keys(monkeypatch):
    """Missing Langfuse keys disables LangChain tracing callbacks."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    assert _build_langfuse_handler() is None


def test_build_langfuse_handler_initializes_client_before_callback(monkeypatch):
    """The Langfuse client is initialized before CallbackHandler is constructed."""
    events: list[tuple] = []

    class FakeLangfuse:
        def __init__(self, *, public_key, secret_key, host):
            events.append(("client", public_key, secret_key, host))

    class FakeCallbackHandler:
        def __init__(self):
            events.append(("handler",))

    fake_langfuse = types.ModuleType("langfuse")
    fake_langfuse.Langfuse = FakeLangfuse
    fake_langchain = types.ModuleType("langfuse.langchain")
    fake_langchain.CallbackHandler = FakeCallbackHandler
    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse)
    monkeypatch.setitem(sys.modules, "langfuse.langchain", fake_langchain)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://example.test")

    handler = _build_langfuse_handler()

    assert isinstance(handler, FakeCallbackHandler)
    assert events == [("client", "pk", "sk", "https://example.test"), ("handler",)]


def test_langchain_config_includes_callbacks_tags_and_metadata(monkeypatch):
    """LangChain config carries callback, provider tags, and run metadata."""
    handler = object()
    monkeypatch.setattr("app.observability._build_langfuse_handler", lambda **_: handler)

    config = langchain_config(
        provider="openai",
        model="gpt",
        prompt_name="summary",
        extra_tags=["per_file"],
        extra_metadata={"file_id": "f1"},
    )

    assert config["callbacks"] == [handler]
    assert config["tags"] == ["openai", "summary", "per_file"]
    assert config["metadata"] == {
        "provider": "openai",
        "model": "gpt",
        "prompt_name": "summary",
        "file_id": "f1",
    }
