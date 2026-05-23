"""Groq provider. Thin wrapper over OpenAIProvider pointed at the Groq API,
rewriting the reported provider name on the returned metadata.
"""
from typing import Type

from pydantic import BaseModel

from app.llm.base import GenerateMetadata
from app.llm.openai import OpenAIProvider


class GroqProvider:
    """LLMProvider that delegates to OpenAIProvider against the Groq endpoint."""

    name = "groq"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        """Wrap an OpenAIProvider configured for the Groq base URL."""
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
        """Delegate to the wrapped OpenAIProvider, then overwrite ``meta.provider`` to ``groq``."""
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
