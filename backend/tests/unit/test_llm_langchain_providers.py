"""LLM providers are backed by LangChain chat model integrations."""
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.llm.groq import GroqProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider
from app.llm.openai_compat import OpenAICompatProvider


def test_openai_provider_uses_chat_openai():
    provider = OpenAIProvider(api_key="test", model="gpt-4.1-mini")

    assert isinstance(provider.chat_model(), ChatOpenAI)
    assert provider.structured_method == "json_schema"
    assert provider.strict_schema is True


def test_openai_compatible_providers_use_json_mode_chat_openai():
    groq = GroqProvider(api_key="test", base_url="https://api.groq.com/openai/v1", model="llama")
    compat = OpenAICompatProvider(api_key="test", base_url="https://example.test/v1", model="model")

    assert isinstance(groq.chat_model(), ChatOpenAI)
    assert isinstance(compat.chat_model(), ChatOpenAI)
    assert groq.name == "groq"
    assert compat.name == "openai_compatible"
    assert groq.structured_method == "json_mode"
    assert compat.structured_method == "json_mode"


def test_ollama_provider_uses_chat_ollama():
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1:8b")

    assert isinstance(provider.chat_model(), ChatOllama)
    assert provider.structured_method == "json_mode"
