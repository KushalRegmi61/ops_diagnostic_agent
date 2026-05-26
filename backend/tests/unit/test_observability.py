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


def test_build_langfuse_handler_uses_cached_client_and_returns_callback_handler(monkeypatch):
    """_build_langfuse_handler delegates client construction to langfuse_client().

    The cached client is consulted first; CallbackHandler is constructed only
    when the client is available, confirming the single-client invariant.
    """
    events: list[str] = []

    sentinel = object()  # stand-in for a real Langfuse client

    class FakeCallbackHandler:
        def __init__(self):
            events.append("handler")

    fake_langchain = types.ModuleType("langfuse.langchain")
    fake_langchain.CallbackHandler = FakeCallbackHandler
    monkeypatch.setitem(sys.modules, "langfuse.langchain", fake_langchain)

    from app import observability
    get_settings.cache_clear()
    observability.langfuse_client.cache_clear()

    # Patch langfuse_client to return a sentinel (non-None = "configured")
    monkeypatch.setattr(observability, "langfuse_client", lambda: sentinel)

    handler = _build_langfuse_handler()

    assert isinstance(handler, FakeCallbackHandler)
    assert events == ["handler"]


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


from unittest.mock import patch


def test_langfuse_client_constructed_once_across_langchain_config_calls(monkeypatch) -> None:
    """langchain_config() must reuse the cached client, not build a fresh one per call."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk_test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk_test")
    from app import observability
    from app.config import get_settings
    get_settings.cache_clear()
    observability.langfuse_client.cache_clear()

    with patch.object(observability, "Langfuse") as MockLF:
        observability.langchain_config(provider="ollama", model="x", prompt_name="p1")
        observability.langchain_config(provider="ollama", model="x", prompt_name="p2")
        observability.langchain_config(provider="ollama", model="x", prompt_name="p3")
        assert MockLF.call_count == 1, (
            f"expected 1 Langfuse client construction, got {MockLF.call_count}"
        )
