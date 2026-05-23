"""Generic OpenAI-compatible provider (Together, Fireworks, vLLM, LiteLLM, etc.).

Identical wiring to GroqProvider — wraps OpenAIProvider with a configurable
base URL and reports its own provider name on the metadata.
"""
from typing import Type

from pydantic import BaseModel

from app.llm.base import GenerateMetadata
from app.llm.openai import OpenAIProvider


class OpenAICompatProvider:
    """LLMProvider for arbitrary OpenAI-API-compatible endpoints."""

    name = "openai_compatible"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        """Wrap an OpenAIProvider configured for the given OpenAI-compatible base URL."""
        self._inner = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        self.model = model

    def generate_json(
        self,
        *,
        prompt_name: str,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> tuple[dict, GenerateMetadata]:
        """Delegate to the wrapped OpenAIProvider, then overwrite ``meta.provider`` to ``openai_compatible``."""
        result, meta = self._inner.generate_json(
            prompt_name=prompt_name,
            prompt=prompt,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            seed=seed,
        )
        meta.provider = self.name
        return result, meta
