"""Generic OpenAI-compatible provider (Together, Fireworks, vLLM, LiteLLM, etc.).

Uses LangChain's ChatOpenAI against a configurable base URL.
"""
from app.llm.openai import OpenAIProvider


class OpenAICompatProvider(OpenAIProvider):
    """LLMProvider for arbitrary OpenAI-API-compatible endpoints."""

    name = "openai_compatible"
    structured_method = "json_mode"
    strict_schema = None

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
