"""Shared LangChain provider helpers."""
from types import SimpleNamespace

from app.llm.langchain_base import token_count


def test_token_count_reads_usage_metadata():
    """LangChain usage_metadata is the preferred token source."""
    msg = SimpleNamespace(usage_metadata={"total_tokens": 42})

    assert token_count(msg) == 42


def test_token_count_reads_openai_response_metadata():
    """OpenAI-style response_metadata token usage is supported."""
    msg = SimpleNamespace(response_metadata={"token_usage": {"total_tokens": 17}})

    assert token_count(msg) == 17
