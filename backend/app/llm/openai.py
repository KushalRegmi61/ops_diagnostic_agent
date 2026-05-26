"""OpenAI provider backed by LangChain's ChatOpenAI integration."""
from langchain_openai import ChatOpenAI

from app.llm.langchain_base import LangChainJSONProvider


class OpenAIProvider(LangChainJSONProvider):
    """LLMProvider using ChatOpenAI with strict structured outputs."""

    name = "openai"
    structured_method = "json_schema"
    strict_schema = True

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def chat_model(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> ChatOpenAI:
        kwargs: dict = {
            "model": self.model,
            "api_key": self.api_key,
            "temperature": temperature,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if seed is not None:
            kwargs["seed"] = seed
        return ChatOpenAI(**kwargs)
