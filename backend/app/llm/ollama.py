"""Local Ollama provider backed by LangChain's ChatOllama integration."""
from langchain_ollama import ChatOllama

from app.llm.langchain_base import LangChainJSONProvider


class OllamaProvider(LangChainJSONProvider):
    """LLMProvider implementation backed by a local Ollama server."""

    name = "ollama"
    structured_method = "json_mode"
    strict_schema = None

    def __init__(self, *, base_url: str, model: str, timeout_s: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def chat_model(
        self,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> ChatOllama:
        kwargs: dict = {
            "model": self.model,
            "base_url": self.base_url,
            "temperature": temperature,
            "format": "json",
            "client_kwargs": {"timeout": self.timeout_s},
        }
        if max_tokens is not None:
            kwargs["num_predict"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if seed is not None:
            kwargs["seed"] = seed
        return ChatOllama(**kwargs)
