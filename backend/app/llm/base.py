"""LLM provider Protocol and the metadata record returned alongside each call.

Every provider implementation in this package conforms to ``LLMProvider`` so
the graph and ReAct tools can treat them uniformly. ``GenerateMetadata`` is
attached to observability spans and run records.
"""
from typing import Protocol, Type

from pydantic import BaseModel


class GenerateMetadata(BaseModel):
    """Structured per-call telemetry: provider, model, token estimate, retries, latency."""

    provider: str
    model: str
    prompt_name: str
    token_estimate: int
    parsed_json: bool
    retry_count: int
    latency_ms: int


class LLMProvider(Protocol):
    """Protocol implemented by every concrete provider in ``app.llm``."""

    name: str

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
        """Generate a JSON object validated against ``schema`` and return it with metadata."""
        ...
